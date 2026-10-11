#!/usr/bin/env python3
"""COG Absorber — Library of Congress straight into the COG library on GitHub (PxD2/cog).

The Library of Congress is a taxpayer trust: held in trust for the people who paid for it, not a government
organization or entity. This digests its texts into COG's dual-number addresses and pushes them to GitHub.
Nothing is kept on this PC: texts are fetched into memory, numbered, committed, and dropped.

    Every distinct meaning  -> one permanent number   (absorbed range starts at 1000)
    Every exact sentence    -> a variant index under that meaning
    (meaning-id, variant-index) is the whole address. A document is just a line of addresses: "1000.0 1007.2 | 1012.0"
                                                                                  ("|" = paragraph break)

What it writes in the repo (all append-only; a file is only ever rewritten while it is still the open one, < 1 MB):
    books/loc-m-0001.json   meaning packs, same format as the hand-made books:  [meaning-id, keys, [first-variant], [variants]]
                            (a later row for an existing meaning continues its variants from [first-variant])
    books/loc-d-0001.json   document packs: title, date, link, and the document as an address sequence
    loc/registry/r-0001.json  lookup segments (hash -> meaning, hash -> address, item -> doc pack)
    loc/state.json          next free meaning-id, open files, where each loc.gov source left off
    books/catalog.json      what the live library site reads to find every book

    python cog_absorber.py --query "Samuel Rutherford" --items 10        # pull, number, push
    python cog_absorber.py --collection century-of-lawmaking --items 25
    python cog_absorber.py --status                                      # what is in the library on GitHub
    python cog_absorber.py --dry-run --query "John Knox" --items 3       # number it, show it, push nothing
    python cog_absorber.py --selftest                                    # offline test with a fake loc.gov and fake GitHub

GitHub sign-in: uses GITHUB_TOKEN / GH_TOKEN, else `gh auth token`, else the token Git already has for github.com.
Standard library only (Python 3.9+). Uses loc_loader.py (polite loc.gov fetching) and cog.py (sentence splitting).
"""
from __future__ import annotations

import argparse, base64, hashlib, json, os, re, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loc_loader as L                      # noqa: E402
from cog import segments, STOP, WORD        # noqa: E402

REPO = "PxD2/cog"
BRANCH = "main"
FIRST_ABSORBED = 1000
PACK_LIMIT = 900_000           # roll to a new file before 1 MB
COMMIT_EVERY = 300_000         # push once this many new bytes are waiting (and always at the end / on STOP)
MIN_TEXT = 200
PARA = re.compile(r"\n[ \t]*\n\s*$")
TRUST = "The Library of Congress is a taxpayer trust: held in trust for the people who paid for it, not a government organization or entity."
UA = "PXD2-COG-Absorber/1.0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def h16(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()


def dumps(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ------------------------------------------------------------------------------------------- meanings
def norm_sentence(seg: str) -> str:
    return re.sub(r"\s+", " ", seg).strip()


def meaning_sig(sentence: str) -> str:
    words = sorted({w.lower() for w in WORD.findall(sentence)} - STOP)
    return " ".join(words) if words else "~" + sentence


def keys_for(sentence: str) -> list[str]:
    out = []
    for w in WORD.findall(sentence):
        w = w.lower()
        if w not in STOP and len(w) > 2 and w not in out:
            out.append(w)
        if len(out) == 5:
            break
    return out or ["~"]


# ------------------------------------------------------------------------------------------- GitHub
def github_token() -> str:
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(k):
            return os.environ[k].strip()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20, creationflags=flags)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    try:
        r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, timeout=120, creationflags=flags)
        for line in r.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


class GitHubStore:
    """Reads the repo at one commit and writes new commits with the Git Data API — no clone, no local copy."""

    def __init__(self, repo: str = REPO, branch: str = BRANCH, token: str | None = None):
        self.repo, self.branch = repo, branch
        self.token = token if token is not None else github_token()
        self.head = ""
        self.tree: dict[str, str] = {}        # path -> blob sha

    def _api(self, method: str, path: str, body=None, raw=False):
        url = path if path.startswith("http") else f"https://api.github.com/repos/{self.repo}/{path}"
        hdr = {"User-Agent": UA, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            hdr["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            hdr["Content-Type"] = "application/json"
        for attempt in range(5):
            try:
                with urlopen(Request(url, data=data, headers=hdr, method=method), timeout=120) as r:
                    out = r.read()
                    return out if raw else json.loads(out or b"null")
            except HTTPError as e:
                if e.code in (500, 502, 503, 504) or (e.code == 403 and "rate" in e.read().decode(errors="ignore").lower()):
                    time.sleep(5 * 2 ** attempt)
                    continue
                raise
        raise RuntimeError(f"GitHub did not answer: {method} {path}")

    def whoami(self) -> str:
        if not self.token:
            return ""
        try:
            return self._api("GET", "https://api.github.com/user").get("login", "")
        except Exception:
            return ""

    def refresh(self) -> None:
        ref = self._api("GET", f"git/ref/heads/{self.branch}")
        self.head = ref["object"]["sha"]
        commit = self._api("GET", f"git/commits/{self.head}")
        tree = self._api("GET", f"git/trees/{commit['tree']['sha']}?recursive=1")
        self.tree = {t["path"]: t["sha"] for t in tree.get("tree", []) if t.get("type") == "blob"}

    def get(self, path: str) -> bytes | None:
        sha = self.tree.get(path)
        if not sha:
            return None
        blob = self._api("GET", f"git/blobs/{sha}")
        return base64.b64decode(blob["content"]) if blob.get("encoding") == "base64" else blob["content"].encode()

    def commit(self, files: dict[str, bytes], message: str) -> str:
        """One commit with every changed file. If someone else pushed meanwhile, rebuild on their head and retry
        (the absorber owns its own files, so nothing of theirs is overwritten)."""
        for attempt in range(4):
            if attempt:
                self.refresh()
            base = self._api("GET", f"git/commits/{self.head}")["tree"]["sha"]
            entries = []
            for path, content in files.items():
                blob = self._api("POST", "git/blobs", {"content": base64.b64encode(content).decode(), "encoding": "base64"})
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
            tree = self._api("POST", "git/trees", {"base_tree": base, "tree": entries})
            c = self._api("POST", "git/commits", {"message": message, "tree": tree["sha"], "parents": [self.head]})
            try:
                self._api("PATCH", f"git/refs/heads/{self.branch}", {"sha": c["sha"], "force": False})
            except HTTPError as e:
                if e.code == 422:
                    continue
                raise
            self.head = c["sha"]
            for e in entries:
                self.tree[e["path"]] = e["sha"]
            return c["sha"]
        raise RuntimeError("could not push: the branch kept moving")


class MemStore:
    """Same interface as GitHubStore, in memory (self-test and dry runs)."""

    def __init__(self, files: dict[str, bytes] | None = None):
        self.files = dict(files or {})
        self.tree = {p: h16(p) for p in self.files}
        self.commits: list[tuple[str, list[str]]] = []
        self.head = "mem"

    def whoami(self) -> str:
        return "memory"

    def refresh(self) -> None:
        self.tree = {p: h16(p) for p in self.files}

    def get(self, path: str) -> bytes | None:
        return self.files.get(path)

    def commit(self, files: dict[str, bytes], message: str) -> str:
        self.files.update(files)
        self.refresh()
        self.commits.append((message, sorted(files)))
        self.head = f"mem{len(self.commits)}"
        return self.head


# ------------------------------------------------------------------------------------------- the library
class Library:
    """The COG library as it stands on GitHub, plus what this run adds. Only open files are ever rewritten."""

    def __init__(self, store, log=print):
        self.store, self.log = store, log
        store.refresh()
        st = store.get("loc/state.json")
        self.state = json.loads(st) if st else {
            "about": "COG absorbed library. " + TRUST, "next_meaning": FIRST_ABSORBED,
            "open": {"m": 1, "d": 1, "r": 1}, "sources": {}, "totals": {"meanings": 0, "variants": 0, "docs": 0, "sentences": 0},
            "updated": now()}
        self.state.setdefault("totals", {}).setdefault("sentences", 0)
        # registry: everything ever assigned (loaded from all segments)
        self.mean: dict[str, int] = {}             # meaning hash -> meaning-id
        self.nvar: dict[int, int] = {}             # meaning-id -> variants so far
        self.var: dict[str, str] = {}              # exact-sentence hash -> "m.v"
        self.items: dict[str, str] = {}            # item hash -> doc pack file ("-" = no usable text / held back)
        segs = sorted(p for p in store.tree if p.startswith("loc/registry/r-") and p.endswith(".json"))
        for p in segs:
            self._absorb_segment(json.loads(store.get(p)))
        if segs:
            self.log(f"Registry: {len(self.mean):,} meanings, {len(self.var):,} exact sentences, {len(self.items):,} items "
                     f"from {len(segs)} segment(s) on GitHub")
        if self.mean:                                   # never hand out a number twice, whatever happened last run
            self.state["next_meaning"] = max(self.state["next_meaning"], max(self.mean.values()) + 1)
        # the open (still growing) files
        o = self.state["open"]
        self.mpack = self._load(self.mfile(o["m"])) or self._new_mpack(o["m"])
        self.dpack = self._load(self.dfile(o["d"])) or self._new_dpack(o["d"])
        self.rseg = self._load(self.rfile(o["r"])) or {"m": {}, "v": {}, "i": {}}
        self._rows = {r[0]: r for r in self.mpack["s"]}
        self._msize, self._rsize = len(dumps(self.mpack)), len(dumps(self.rseg))
        cat = self._load("books/catalog.json") or {}
        self.ranges = {b["file"]: {k: b.get(k) for k in ("from", "to", "cont")}
                       for b in cat.get("books", []) if b.get("room") == "loc" and b.get("kind") == "meanings"}
        self.dirty: set[str] = set()
        self.pending = 0

    # file names
    @staticmethod
    def mfile(n): return f"books/loc-m-{n:04d}.json"
    @staticmethod
    def dfile(n): return f"books/loc-d-{n:04d}.json"
    @staticmethod
    def rfile(n): return f"loc/registry/r-{n:04d}.json"

    def _load(self, path):
        b = self.store.get(path)
        return json.loads(b) if b else None

    def _new_mpack(self, n):
        return {"name": f"loc-m-{n:04d}", "ver": 1, "w": 2, "crc": 0, "src": "loc.gov", "trust": TRUST, "s": []}

    def _new_dpack(self, n):
        return {"name": f"loc-d-{n:04d}", "ver": 1, "kind": "docs", "src": "loc.gov", "trust": TRUST,
                "note": "seq = meaning.variant addresses; | = paragraph break", "docs": []}

    def _absorb_segment(self, seg: dict) -> None:
        for h, m in seg.get("m", {}).items():
            self.mean[h] = m
        for h, addr in seg.get("v", {}).items():
            self.var[h] = addr
            m, v = map(int, addr.split("."))
            if v + 1 > self.nvar.get(m, 0):
                self.nvar[m] = v + 1
        self.items.update(seg.get("i", {}))

    # numbering
    def address(self, sentence: str) -> str:
        vh = h16(sentence)
        a = self.var.get(vh)
        if a:
            return a
        mh = h16(meaning_sig(sentence))
        m = self.mean.get(mh)
        if m is None:                                   # a new meaning: next free number
            m = self.state["next_meaning"]
            self.state["next_meaning"] = m + 1
            self.mean[mh] = self.rseg["m"][mh] = m
            self.state["totals"]["meanings"] += 1
            v = 0
            row = [m, keys_for(sentence), [0], [sentence]]
            self.mpack["s"].append(row)
        else:                                           # a new exact wording of a known meaning
            v = self.nvar.get(m, 0)
            row = self._rows.get(m)                     # a row for m already in the open pack: extend it
            if row is not None and row[2][0] + len(row[3]) == v:
                row[3].append(sentence)
            else:
                row = [m, [], [v], [sentence]]
                self.mpack["s"].append(row)
        self._rows[m] = row
        self.nvar[m] = v + 1
        a = f"{m}.{v}"
        self.var[vh] = self.rseg["v"][vh] = a
        self.state["totals"]["variants"] += 1
        self.pending += len(sentence) + 30
        self._msize += len(sentence.encode()) + 24
        self._rsize += 64
        self.dirty |= {"m", "r"}
        if self._msize > PACK_LIMIT:
            self._roll("m")
        if self._rsize > PACK_LIMIT:
            self._roll("r")
        return a

    def seen(self, item_id: str) -> bool:
        return h16(item_id) in self.items

    def mark(self, item_id: str, where: str) -> None:
        h = h16(item_id)
        self.items[h] = self.rseg["i"][h] = where
        self.dirty.add("r")

    def add_doc(self, item_id: str, meta: dict, text: str) -> int:
        seq, n = [], 0
        for seg in segments(text):
            sent = norm_sentence(seg)
            if sent:
                seq.append(self.address(sent))
                n += 1
            if PARA.search(seg) and seq and seq[-1] != "|":
                seq.append("|")
        while seq and seq[-1] == "|":
            seq.pop()
        parts, cur, size = [], [], 0                    # a huge document spans entries, never splitting an address
        for tok in seq:
            if size + len(tok) + 1 > 600_000 and cur:
                parts.append(" ".join(cur)); cur, size = [], 0
            cur.append(tok); size += len(tok) + 1
        parts.append(" ".join(cur))
        for i, p in enumerate(parts):
            entry = dict(meta, id=item_id, n=n, chars=len(text), seq=p, at=now())
            if len(parts) > 1:
                entry["part"] = f"{i + 1}/{len(parts)}"
            if len(dumps(self.dpack)) + len(p) > PACK_LIMIT and self.dpack["docs"]:
                self._roll("d")
            self.dpack["docs"].append(entry)
            self.pending += len(p) + 200
        self.dirty.add("d")
        self.mark(item_id, self.dfile(self.state["open"]["d"]))
        self.state["totals"]["docs"] += 1
        self.state["totals"]["sentences"] += n
        self._maybe_roll()
        return n

    # files
    def _roll(self, kind: str) -> None:
        """Close the open file (it never changes again) and open the next one. Everything waiting is pushed in the
        same commit, so the registry on GitHub always covers every number already used."""
        closing = self._files_for({kind})
        name = list(closing)[0]
        if kind == "m":
            self.ranges[name] = self._range(self.mpack)
        files = self._files_for(self.dirty | {kind})
        self.state["open"][kind] += 1
        n = self.state["open"][kind]
        if kind == "m":
            self.mpack, self._rows = self._new_mpack(n), {}
            self._msize = len(dumps(self.mpack))
        elif kind == "d":
            self.dpack = self._new_dpack(n)
        else:
            self.rseg = {"m": {}, "v": {}, "i": {}}
            self._rsize = 20
        self.dirty.discard(kind)
        self._commit(files, f"COG: close {name} (< 1 MB); open {kind}-{n:04d}")
        self.dirty.clear()
        self.pending = 0
        self.log(f"  closed {name}; next is {kind}-{n:04d}")

    def _maybe_roll(self) -> None:
        self._msize, self._rsize = len(dumps(self.mpack)), len(dumps(self.rseg))
        if self._msize > PACK_LIMIT:
            self._roll("m")
        if self._rsize > PACK_LIMIT:
            self._roll("r")

    def _files_for(self, kinds: set[str]) -> dict[str, bytes]:
        o, out = self.state["open"], {}
        if "m" in kinds:
            out[self.mfile(o["m"])] = dumps(self.mpack)
        if "d" in kinds:
            out[self.dfile(o["d"])] = dumps(self.dpack)
        if "r" in kinds:
            out[self.rfile(o["r"])] = dumps(self.rseg)
        return out

    def catalog(self, tree_paths) -> dict:
        own = {"cog-english-v0": ("English", "Inquiry into situation, status, activity."),
               "cog-physics-v0": ("Physics", "Core physical meanings."),
               "cog-philosophy-v0": ("Philosophy", "Foundational meanings.")}
        books = []
        for p in sorted(tree_paths):
            if not (p.startswith("books/") and p.endswith(".json")) or p == "books/catalog.json":
                continue
            name = p[6:-5]
            if name.startswith("loc-m-"):
                books.append({"file": p, "kind": "meanings", "room": "loc"})
            elif name.startswith("loc-d-"):
                books.append({"file": p, "kind": "docs", "room": "loc"})
            else:
                t, b = own.get(name, (name, ""))
                books.append({"file": p, "kind": "meanings", "room": name, "title": t, "blurb": b})
        open_m = self.mfile(self.state["open"]["m"])
        for b in books:
            if b["room"] == "loc" and b["kind"] == "meanings":
                b.update(self._range(self.mpack) if b["file"] == open_m else self.ranges.get(b["file"], {}))
        return {"name": "COG catalog", "updated": now(), "trust": TRUST, "next_meaning": self.state["next_meaning"],
                "totals": self.state["totals"], "books": books}

    @staticmethod
    def _range(pack) -> dict:
        new = [r[0] for r in pack["s"] if r[2] == [0]]
        return {"from": min(new) if new else None, "to": max(new) if new else None,
                "cont": sorted({r[0] for r in pack["s"] if r[2] != [0]})}

    def _commit(self, files: dict[str, bytes], message: str) -> str:
        self.state["updated"] = now()
        files = dict(files)
        files["loc/state.json"] = dumps(self.state)
        paths = set(self.store.tree) | set(files)
        files["books/catalog.json"] = json.dumps(self.catalog(paths), ensure_ascii=False, indent=1).encode()
        return self.store.commit(files, message)

    def flush(self, message: str) -> str | None:
        if not self.dirty:
            return None
        sha = self._commit(self._files_for(self.dirty), message)
        self.dirty.clear()
        self.pending = 0
        return sha


# ------------------------------------------------------------------------------------------- rights
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
OPEN = re.compile(r"no known restrictions|public domain|free to use|not subject to copyright|no known copyright", re.I)


def rights_ok(meta: dict, item_json: dict | None, cutoff: int = 1930) -> tuple[bool, str]:
    """Hold back anything that may still be under copyright: the GitHub library is public."""
    years = [int(y) for y in YEAR.findall(meta.get("date", ""))]
    if years and min(years) < cutoff:
        return True, f"published {min(years)}"
    rights = ""
    if item_json:
        it = item_json.get("item") or {}
        rights = " ".join(L.as_text(it.get(k)) for k in ("rights_advisory", "rights", "rights_information"))
        rights += " " + L.as_text(item_json.get("rights"))
    if OPEN.search(rights):
        return True, "open rights statement"
    return False, "date after %d and no open-rights statement" % cutoff


# ------------------------------------------------------------------------------------------- the run
class Absorber:
    def __init__(self, store, fetcher=None, log=print, progress=None, stop: threading.Event | None = None,
                 rights_gate: bool = True, per_page: int = 25):
        self.store, self.log = store, log
        self.fetcher = fetcher or L.Fetcher(slow=90)
        self.progress = progress or (lambda done, total, label: None)
        self.stop = stop or threading.Event()
        self.rights_gate, self.per_page = rights_gate, per_page

    def run(self, sources: list[str], max_items: int, max_pages: int = 20) -> dict:
        lib = Library(self.store, self.log)
        start = dict(lib.state["totals"])
        got, held, empty = 0, 0, 0
        last_sha = None
        for src in sources:
            if self.stop.is_set() or got >= max_items:
                break
            prog = lib.state["sources"].setdefault(src, {"next": L.start_url(src, self.per_page), "pages": 0, "done": False})
            if prog.get("done"):
                self.log(f"{src}: already fully absorbed")
                continue
            url, pages = prog["next"], 0
            self.log(f"{src}: catalogue page {prog['pages'] + 1}")
            while url and got < max_items and pages < max_pages and not self.stop.is_set():
                data = self.fetcher.get_json(url)
                if not isinstance(data, dict):
                    self.log(f"  loc.gov did not answer for {url} — try again later (place kept)")
                    break
                results = [r for r in (data.get("results") or []) if isinstance(r, dict)]
                page_complete = True
                for rec in results:
                    if self.stop.is_set() or got >= max_items:
                        page_complete = False
                        break
                    item_id = L.as_text(rec.get("id") or rec.get("url"))
                    if not item_id or lib.seen(item_id):
                        continue
                    meta = {"title": L.as_text(rec.get("title"))[:300], "date": L.as_text(rec.get("date") or rec.get("dates"))[:40],
                            "url": L.as_text(rec.get("url") or item_id), "source": src}
                    api = L.item_api_url(item_id)
                    ij = self.fetcher.get_json(api) if api else None
                    ij = ij if isinstance(ij, dict) else None
                    if self.rights_gate:
                        ok, why = rights_ok(meta, ij)
                        if not ok:
                            lib.mark(item_id, "-held")
                            held += 1
                            self.log(f"  held back ({why}): {meta['title'][:70]}")
                            continue
                    text = ""
                    found = L.find_text_url(ij) if ij else None
                    if found:
                        kind, turl = found
                        raw = self.fetcher.get_bytes(turl)
                        if isinstance(raw, (bytes, bytearray)):
                            text = L.to_text(kind, turl, raw)
                    if len(text) < MIN_TEXT:
                        lib.mark(item_id, "-")
                        empty += 1
                        self.log(f"  no text online: {meta['title'][:70]}")
                        continue
                    before = lib.state["totals"]["meanings"]
                    n = lib.add_doc(item_id, meta, text)
                    got += 1
                    self.log(f"  [{got}/{max_items}] {n:,} sentences · +{lib.state['totals']['meanings'] - before:,} new meanings · {meta['title'][:70]}")
                    self.progress(got, max_items, meta["title"])
                    del text
                    if lib.pending >= COMMIT_EVERY:
                        last_sha = lib.flush(f"COG absorb: +{got} documents from loc.gov ({src})")
                        self.log(f"  pushed to GitHub {str(last_sha)[:7]}")
                if page_complete:
                    pages += 1
                    prog["pages"] += 1
                    nxt = (data.get("pagination") or {}).get("next")
                    prog["next"], prog["done"] = nxt, not nxt
                    lib.dirty.add("r")
                    url = nxt
                else:
                    break
            prog["updated"] = now()
        t = lib.state["totals"]
        add = {k: t[k] - start.get(k, 0) for k in t}
        if lib.dirty or got or held or empty:
            lib.dirty.add("r")
            last_sha = lib.flush(f"COG absorb: +{add['docs']} documents, +{add['meanings']} meanings, +{add['variants']} sentences (loc.gov)") or last_sha
        summary = {"docs": add["docs"], "meanings": add["meanings"], "variants": add["variants"], "sentences": add["sentences"],
                   "held_back": held, "no_text": empty, "next_meaning": lib.state["next_meaning"], "commit": last_sha,
                   "stopped": self.stop.is_set(), "totals": t}
        self.log(f"Done: +{add['docs']} documents · +{add['meanings']:,} meanings · +{add['variants']:,} exact sentences"
                 f" · next free meaning-id {lib.state['next_meaning']}" + (f" · commit {last_sha[:7]}" if last_sha else ""))
        return summary


def decode(store, seq: str) -> str:
    """Rebuild a document from its addresses (for checking)."""
    rows: dict[int, list[tuple[int, list[str]]]] = {}
    for p in sorted(store.tree):
        if p.startswith("books/loc-m-"):
            for r in json.loads(store.get(p))["s"]:
                rows.setdefault(r[0], []).append((r[2][0], r[3]))
    out, para = [], []
    for tok in seq.split():
        if tok == "|":
            out.append(" ".join(para)); para = []
            continue
        m, v = map(int, tok.split("."))
        for start, vs in rows[m]:
            if start <= v < start + len(vs):
                para.append(vs[v - start]); break
    out.append(" ".join(para))
    return "\n\n".join(x for x in out if x)


def status(store) -> dict:
    store.refresh()
    st = store.get("loc/state.json")
    return json.loads(st) if st else {"next_meaning": FIRST_ABSORBED, "totals": {"meanings": 0, "variants": 0, "docs": 0, "sentences": 0}, "sources": {}}


# ------------------------------------------------------------------------------------------- self-test
def selftest() -> None:
    para = ("Congress shall have power to lay and collect taxes. The power to lay and collect taxes, Congress shall have. "
            "Congress shall have Power To lay and collect Taxes!\n\nIt is so ordered. It is so ordered.\n\n")
    texts = {"a": para * 3 + "A law against tyrants is no law. " * 2, "b": "It is so ordered. " + "Lex rex: the law is king. " * 20,
             "c": "Modern work under copyright. " * 20}
    pages = {
        "https://www.loc.gov/search/?q=test&fo=json&c=25&sp=1": {"pagination": {"next": "https://www.loc.gov/search/?q=test&fo=json&c=25&sp=2"},
            "results": [{"id": "http://www.loc.gov/item/a/", "title": "Item A", "date": "1789"},
                        {"id": "http://www.loc.gov/item/c/", "title": "Item C", "date": "1990"}]},
        "https://www.loc.gov/search/?q=test&fo=json&c=25&sp=2": {"pagination": {}, "results": [{"id": "http://www.loc.gov/item/b/", "title": "Item B", "date": "1644"}]},
    }

    class FakeFetcher:
        def get_json(self, url):
            if url in pages:
                return pages[url]
            k = url.rstrip("/").split("/")[-2] if "?fo=json" in url else ""
            k = url.split("/item/")[1].split("/")[0] if "/item/" in url else k
            return {"item": {"rights_advisory": "Rights status not evaluated"}, "resources": [{"files": [[{"mimetype": "text/plain", "url": f"https://tile.loc.gov/{k}.txt"}]]}]}

        def get_bytes(self, url):
            return texts[url.rsplit("/", 1)[1][:-4]].encode()

    logs: list[str] = []
    store = MemStore()
    r = Absorber(store, FakeFetcher(), log=logs.append).run(["q:test"], max_items=10)
    assert r["docs"] == 2 and r["held_back"] == 1, r
    st = json.loads(store.files["loc/state.json"])
    assert st["sources"]["q:test"]["done"] is True
    d = json.loads(store.files["books/loc-d-0001.json"])["docs"]
    seqA = d[0]["seq"]
    first = seqA.split()[:3]
    assert first == ["1000.0", "1000.1", "1000.2"], first           # same meaning, three exact wordings
    assert "|" in seqA
    back = decode(store, seqA)
    assert back.startswith("Congress shall have power to lay and collect taxes. The power to lay and collect taxes, Congress shall have."), back[:80]
    assert "It is so ordered." in back
    m = json.loads(store.files["books/loc-m-0001.json"])
    assert m["s"][0][:3] == [1000, ["congress", "power", "lay", "collect", "taxes"], [0]], m["s"][0]
    cat = json.loads(store.files["books/catalog.json"])
    assert any(b["file"] == "books/loc-m-0001.json" and b["from"] == 1000 for b in cat["books"])
    # second run: nothing new, addresses never change, the doc is not re-absorbed
    before = dict(store.files)
    r2 = Absorber(store, FakeFetcher(), log=logs.append).run(["q:test"], max_items=10)
    assert r2["docs"] == 0 and store.files["books/loc-m-0001.json"] == before["books/loc-m-0001.json"]
    # a new wording of a known meaning in a later run continues the variant numbers (append-only)
    pages["https://www.loc.gov/search/?q=more&fo=json&c=25&sp=1"] = {"pagination": {}, "results": [{"id": "http://www.loc.gov/item/e/", "title": "E", "date": "1700"}]}
    texts["e"] = "Taxes: Congress shall have power to lay and collect them. " * 10 + "To lay and collect taxes, Congress shall have power."
    lib = Library(store, log=logs.append)
    nv = lib.nvar[1000]
    Absorber(store, FakeFetcher(), log=logs.append).run(["q:more"], max_items=5)
    lib2 = Library(store, log=logs.append)
    assert lib2.nvar[1000] == nv + 1, (nv, lib2.nvar[1000])
    e_seq = [x for x in json.loads(store.files["books/loc-d-0001.json"])["docs"] if x["title"] == "E"][0]["seq"]
    assert decode(store, e_seq).endswith("To lay and collect taxes, Congress shall have power.")
    # rolling packs stays under 1 MB
    global PACK_LIMIT
    old, PACK_LIMIT = PACK_LIMIT, 3000
    try:
        pages["https://www.loc.gov/search/?q=big&fo=json&c=25&sp=1"] = {"pagination": {}, "results": [{"id": "http://www.loc.gov/item/f/", "title": "F", "date": "1600"}]}
        texts["f"] = " ".join(f"Sentence number {w} about subject {w * 7}." for w in range(400))
        Absorber(store, FakeFetcher(), log=logs.append).run(["q:big"], max_items=5)
    finally:
        PACK_LIMIT = old
    packs = [p for p in store.files if p.startswith("books/loc-m-")]
    assert len(packs) > 3, packs
    f_seq = " ".join(x["seq"] for x in json.loads(store.files[max(p for p in store.files if p.startswith("books/loc-d-"))])["docs"] if x["title"] == "F")
    assert decode(store, f_seq).startswith("Sentence number 0 about subject 0. Sentence number 1"), decode(store, f_seq)[:60]
    print(f"selftest ok · {len(store.commits)} commits · {len(packs)} meaning packs · next meaning {json.loads(store.files['loc/state.json'])['next_meaning']}")


# ------------------------------------------------------------------------------------------- command line
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", action="append", default=[], help="loc.gov search words (repeatable)")
    ap.add_argument("--collection", action="append", default=[], help="loc.gov collection slug (repeatable)")
    ap.add_argument("--books", action="store_true", help="searches: books / printed text only")
    ap.add_argument("--items", type=int, default=10, help="documents to absorb this run")
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--no-rights-gate", action="store_true", help="absorb items even if they may be under copyright")
    ap.add_argument("--dry-run", action="store_true", help="number everything in memory, push nothing")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    store = MemStore() if a.dry_run else GitHubStore(a.repo, a.branch)
    if not a.dry_run and not store.token:
        print("No GitHub sign-in found. Run `gh auth login`, or set GITHUB_TOKEN, or push once with Git so it remembers you.")
        return 2
    if a.status:
        print(json.dumps(status(store), indent=1)[:4000])
        return 0
    sources = [f"q:{q}" + (L.BOOKS_TAG if a.books else "") for q in a.query] + list(a.collection)
    if not sources:
        ap.error("give at least one --query or --collection")
    if hasattr(L, "no_console_freeze"):
        try:
            L.no_console_freeze()
        except Exception:
            pass
    r = Absorber(store, rights_gate=not a.no_rights_gate).run(sources, a.items, a.max_pages)
    if a.dry_run:
        for p, b in sorted(store.files.items()):
            print(f"  would push {p}  ({len(b):,} bytes)")
    return 0 if not r.get("stopped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
