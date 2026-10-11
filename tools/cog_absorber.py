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
    books/core-m-0001.json   meaning packs, same format as the hand-made books:  [meaning-id, keys, [first-variant], [variants]]
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
import archives as AR                       # noqa: E402
from cog import segments, STOP, WORD        # noqa: E402

REPO = "PxD2/cog"
BRANCH = "main"
FIRST_ABSORBED = 1000
PACK_LIMIT = 900_000           # roll to a new file before 1 MB
COMMIT_EVERY = 300_000         # push once this many new bytes are waiting (and always at the end / on STOP)
MIN_TEXT = 200
YEAR1 = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
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


class LocalStore:
    """Same interface, on a folder (a git working tree). commit() writes the files; push with git yourself."""

    def __init__(self, root):
        self.root = Path(root)
        self.tree: dict[str, str] = {}
        self.head = "local"
        self.branch = BRANCH

    def whoami(self) -> str:
        return "local"

    def refresh(self) -> None:
        self.tree = {p.relative_to(self.root).as_posix(): "x" for p in self.root.rglob("*")
                     if p.is_file() and ".git" not in p.parts}

    def get(self, path: str) -> bytes | None:
        p = self.root / path
        return p.read_bytes() if p.is_file() else None

    def commit(self, files: dict[str, bytes], message: str) -> str:
        for path, b in files.items():
            p = self.root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b)
            self.tree[path] = "x"
        return "local"


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

    def __init__(self, store, log=print, store_for=None):
        self.store, self.log = store, log
        self.store_for = store_for or (lambda repo: GitHubStore(repo, getattr(store, "branch", BRANCH), getattr(store, "token", None)))
        self.ext: dict[str, object] = {}           # section repos opened this run
        store.refresh()
        st = store.get("loc/state.json")
        self.state = json.loads(st) if st else {
            "about": "COG absorbed library. " + TRUST, "next_meaning": FIRST_ABSORBED,
            "open": {"m": 1, "r": 1}, "sections": {}, "sources": {}, "totals": {"meanings": 0, "variants": 0, "docs": 0, "sentences": 0},
            "updated": now()}
        self.state.setdefault("totals", {}).setdefault("sentences", 0)
        self.state.setdefault("sections", {})
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
        self.dpacks: dict[str, dict] = {}            # section -> its open document pack (loaded when first used)
        self.ipacks: dict[str, dict] = {}            # section -> its open finder index (always kept in core)
        self.rseg = self._load(self.rfile(o["r"])) or {"m": {}, "v": {}, "i": {}}
        self._rows = {r[0]: r for r in self.mpack["s"]}
        self._msize, self._rsize = len(dumps(self.mpack)), len(dumps(self.rseg))
        cat = self._load("books/catalog.json") or {}
        self.ranges = {b["file"]: {k: b.get(k) for k in ("from", "to", "cont")}
                       for b in cat.get("books", []) if b.get("room") == "core" and b.get("kind") == "meanings"}
        self.dirty: set[str] = set()
        self.pending = 0

    # file names
    @staticmethod
    def mfile(n): return f"books/core-m-{n:04d}.json"
    @staticmethod
    def dfile(sec, n): return f"sections/{sec}/docs-{n:04d}.json"
    @staticmethod
    def ifile(sec, n): return f"sections/{sec}/index-{n:04d}.json"
    @staticmethod
    def rfile(n): return f"loc/registry/r-{n:04d}.json"

    def _load(self, path):
        b = self.store.get(path)
        return json.loads(b) if b else None

    def _new_mpack(self, n):
        return {"name": f"core-m-{n:04d}", "ver": 1, "w": 2, "crc": 0, "src": "loc.gov", "trust": TRUST, "s": []}

    def _new_dpack(self, sec, n):
        return {"name": f"{sec}/docs-{n:04d}", "ver": 1, "kind": "docs", "section": sec, "src": "loc.gov", "trust": TRUST,
                "note": "seq = meaning.variant addresses (meanings live in the core books/); | = paragraph break", "docs": []}

    # sections: groups of documents, each with its own storage spot. Meaning-ids stay global (one registry in core).
    def section(self, sec: str, title: str = "", store: str = "core") -> dict:
        sec = re.sub(r"[^a-z0-9-]+", "-", sec.lower()).strip("-") or "general"
        st = self.state["sections"].get(sec)
        if st is None:
            st = self.state["sections"][sec] = {"title": title or sec.replace("-", " ").title(), "store": store or "core",
                                                "open": 1, "docs": 0, "sentences": 0, "created": now()}
            self.log(f"New section: {st['title']} (stored in {'core' if st['store'] == 'core' else st['store']})")
        elif store and store != st["store"]:
            self.log(f"  section {sec} already lives in {st['store']}; keeping it there (moving a section is a separate job)")
        return st

    def _sec_store(self, sec: str):
        repo = self.state["sections"][sec]["store"]
        if repo == "core":
            return self.store
        if repo not in self.ext:
            s = self.store_for(repo)
            s.refresh()
            self.ext[repo] = s
        return self.ext[repo]

    def _ipack(self, sec: str) -> dict:
        if sec not in self.ipacks:
            n = self.state["sections"][sec].setdefault("iopen", 1)
            self.ipacks[sec] = self._load(self.ifile(sec, n)) or {"name": f"{sec}/index-{n:04d}", "ver": 1, "section": sec,
                "note": "finder index: t=title y=year d=date s=subject p=place k=kind f=docs file no. i=position", "e": []}
        return self.ipacks[sec]

    def _index(self, sec: str, e: dict) -> None:
        ip = self._ipack(sec)
        if len(dumps(ip)) + len(dumps(e)) > PACK_LIMIT and ip["e"]:
            self._roll("i:" + sec)
            ip = self._ipack(sec)
        ip["e"].append({k: v for k, v in e.items() if v not in (None, "", [], {})})
        self.dirty.add("i:" + sec)

    def _dpack(self, sec: str) -> dict:
        if sec not in self.dpacks:
            n = self.state["sections"][sec]["open"]
            b = self._sec_store(sec).get(self.dfile(sec, n))
            self.dpacks[sec] = json.loads(b) if b else self._new_dpack(sec, n)
        return self.dpacks[sec]

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

    def encode(self, text: str) -> tuple[list[str], int]:
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
        return seq, n

    def _place(self, sec: str, entry: dict) -> tuple[int, int]:
        dp = self._dpack(sec)
        if len(dumps(dp)) + len(dumps(entry)) > PACK_LIMIT and dp["docs"]:
            self._roll("d:" + sec)
            dp = self._dpack(sec)
        dp["docs"].append(entry)
        self.dirty.add("d:" + sec)
        return self.state["sections"][sec]["open"], len(dp["docs"]) - 1

    def add_article(self, key: str, sec: str, art: dict) -> int:
        """An encyclopedia article: several reading levels, each stored as an address line, plus quiz and facts."""
        if sec not in self.state["sections"]:
            self.section(sec)
        sst = self.state["sections"][sec]
        levels, n = {}, 0
        for lvl, text in (art.get("texts") or {}).items():
            if text:
                seq, k = self.encode(text)
                levels[lvl] = " ".join(seq)
                n += k
        entry = {"id": art["id"], "kind": "article", "title": art["title"], "subject": art.get("subject"), "year": art.get("year"),
                 "place": art.get("place"), "related": art.get("related"), "summary": art.get("summary"), "quiz": art.get("quiz"),
                 "levels": levels, "n": n, "at": now()}
        f, i = self._place(sec, entry)
        self._index(sec, {"id": art["id"], "k": "article", "t": art["title"], "s": art.get("subject"), "y": art.get("year"),
                          "p": art.get("place"), "sum": (art.get("summary") or "")[:240], "rel": art.get("related"), "f": f, "i": i})
        self.pending += sum(len(x) for x in levels.values()) + 400
        self.mark(key, f"{sec}:{self.dfile(sec, f)}")
        self.state["totals"]["docs"] += 1
        self.state["totals"]["sentences"] += n
        sst["docs"] += 1
        sst["sentences"] += n
        self._maybe_roll()
        return n

    def add_doc(self, item_id: str, meta: dict, text: str, sec: str = "general") -> int:
        if sec not in self.state["sections"]:
            self.section(sec)
        sst = self.state["sections"][sec]
        seq, n = self.encode(text)
        parts, cur, size = [], [], 0                    # a huge document spans entries, never splitting an address
        for tok in seq:
            if size + len(tok) + 1 > 600_000 and cur:
                parts.append(" ".join(cur)); cur, size = [], 0
            cur.append(tok); size += len(tok) + 1
        parts.append(" ".join(cur))
        ym = YEAR1.search(meta.get("date", "") or "")
        for i, p in enumerate(parts):
            entry = dict(meta, id=item_id, n=n, chars=len(text), seq=p, at=now())
            if i:
                entry.pop("media", None)
            if len(parts) > 1:
                entry["part"] = f"{i + 1}/{len(parts)}"
            f, pos = self._place(sec, entry)
            if i == 0:
                media = meta.get("media") or []
                self._index(sec, {"id": item_id, "k": meta.get("kind") or "doc", "t": meta.get("title"), "y": int(ym.group(1)) if ym else None,
                                  "pr": meta.get("pres"), "oc": meta.get("occasion"), "w": meta.get("words"),
                                  "d": meta.get("date"), "f": f, "i": pos, "n": n, "parts": len(parts) if len(parts) > 1 else None,
                                  "fm": meta.get("format"), "th": meta.get("thumb"), "ar": meta.get("archive"),
                                  "mv": sum(1 for m in media if m["type"] in ("video", "audio")) or None})
            self.pending += len(p) + 200
        self.mark(item_id, f"{sec}:{self.dfile(sec, sst['open'])}")
        self.state["totals"]["docs"] += 1
        self.state["totals"]["sentences"] += n
        sst["docs"] += 1
        sst["sentences"] += n
        self._maybe_roll()
        return n

    # files
    def _roll(self, kind: str) -> None:
        """Close the open file (it never changes again) and open the next one. Everything waiting is pushed in the
        same commit, so the registry on GitHub always covers every number already used."""
        core, ext = self._files_for({kind})
        name = (list(core) or [p for f in ext.values() for p in f])[0]
        if kind == "m":
            self.ranges[name] = self._range(self.mpack)
        core, ext = self._files_for(self.dirty | {kind})
        if kind.startswith("d:"):
            sec = kind[2:]
            self.state["sections"][sec]["open"] += 1
            n = self.state["sections"][sec]["open"]
            self.dpacks[sec] = self._new_dpack(sec, n)
        elif kind.startswith("i:"):
            sec = kind[2:]
            self.state["sections"][sec]["iopen"] = self.state["sections"][sec].get("iopen", 1) + 1
            n = self.state["sections"][sec]["iopen"]
            self.ipacks.pop(sec, None)
        else:
            self.state["open"][kind] += 1
            n = self.state["open"][kind]
        if kind == "m":
            self.mpack, self._rows = self._new_mpack(n), {}
            self._msize = len(dumps(self.mpack))
        elif kind.startswith(("d:", "i:")):
            pass
        else:
            self.rseg = {"m": {}, "v": {}, "i": {}}
            self._rsize = 20
        self.dirty.discard(kind)
        self._commit(core, ext, f"COG: close {name} (< 1 MB); next {n:04d}")
        self.dirty.clear()
        self.pending = 0
        self.log(f"  closed {name}; next file {n:04d}")

    def _maybe_roll(self) -> None:
        self._msize, self._rsize = len(dumps(self.mpack)), len(dumps(self.rseg))
        if self._msize > PACK_LIMIT:
            self._roll("m")
        if self._rsize > PACK_LIMIT:
            self._roll("r")

    def _files_for(self, kinds: set[str]) -> tuple[dict[str, bytes], dict[str, dict[str, bytes]]]:
        """(files for the core repo, {section repo: files})"""
        o, core, ext = self.state["open"], {}, {}
        if "m" in kinds:
            core[self.mfile(o["m"])] = dumps(self.mpack)
        if "r" in kinds:
            core[self.rfile(o["r"])] = dumps(self.rseg)
        for k in kinds:
            if k.startswith("d:") and k[2:] in self.dpacks:
                sec = k[2:]
                st = self.state["sections"][sec]
                f = {self.dfile(sec, st["open"]): dumps(self.dpacks[sec])}
                (core.update(f) if st["store"] == "core" else ext.setdefault(st["store"], {}).update(f))
            if k.startswith("i:") and k[2:] in self.ipacks:
                sec = k[2:]
                core[self.ifile(sec, self.state["sections"][sec].get("iopen", 1))] = dumps(self.ipacks[sec])
        return core, ext

    def catalog(self, tree_paths) -> dict:
        own = {"cog-english-v0": ("English", "Inquiry into situation, status, activity."),
               "cog-physics-v0": ("Physics", "Core physical meanings."),
               "cog-philosophy-v0": ("Philosophy", "Foundational meanings.")}
        books = []
        for p in sorted(tree_paths):
            if not (p.startswith("books/") and p.endswith(".json")) or p == "books/catalog.json":
                continue
            name = p[6:-5]
            if name.startswith("core-m-"):
                books.append({"file": p, "kind": "meanings", "room": "core"})
            else:
                t, b = own.get(name, (name, ""))
                books.append({"file": p, "kind": "meanings", "room": name, "title": t, "blurb": b})
        open_m = self.mfile(self.state["open"]["m"])
        for b in books:
            if b["room"] == "core" and b["kind"] == "meanings":
                b.update(self._range(self.mpack) if b["file"] == open_m else self.ranges.get(b["file"], {}))
        sections = []
        for sec, st in self.state["sections"].items():
            base = "" if st["store"] == "core" else f"https://raw.githubusercontent.com/{st['store']}/{getattr(self.store, 'branch', BRANCH)}/"
            sections.append({"id": sec, "title": st["title"], "store": st["store"], "base": base, "docs": st["docs"],
                             "sentences": st["sentences"], "files": [self.dfile(sec, i) for i in range(1, st["open"] + 1)],
                             "index": [self.ifile(sec, i) for i in range(1, st.get("iopen", 1) + 1)]})
        return {"name": "COG catalog", "updated": now(), "trust": TRUST, "next_meaning": self.state["next_meaning"],
                "totals": self.state["totals"], "books": books, "sections": sections}

    @staticmethod
    def _range(pack) -> dict:
        new = [r[0] for r in pack["s"] if r[2] == [0]]
        return {"from": min(new) if new else None, "to": max(new) if new else None,
                "cont": sorted({r[0] for r in pack["s"] if r[2] != [0]})}

    def _commit(self, files: dict[str, bytes], ext: dict[str, dict[str, bytes]], message: str) -> str:
        """Section repos first, then core (registry + state) — so core never points at a document that is not there."""
        for repo, f in ext.items():
            self.ext[repo].commit(f, message)
        self.state["updated"] = now()
        files = dict(files)
        files["loc/state.json"] = dumps(self.state)
        paths = set(self.store.tree) | set(files)
        files["books/catalog.json"] = json.dumps(self.catalog(paths), ensure_ascii=False, indent=1).encode()
        return self.store.commit(files, message)

    def flush(self, message: str) -> str | None:
        if not self.dirty:
            return None
        core, ext = self._files_for(self.dirty)
        sha = self._commit(core, ext, message)
        self.dirty.clear()
        self.pending = 0
        return sha


# ------------------------------------------------------------------------------------------- rights
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
OPEN = re.compile(r"no known restrictions|public domain|publicdomain|free to use|not subject to copyright|no known copyright|"
                  r"creativecommons\.org/licenses/by(-sa)?/", re.I)


def rights_ok(meta: dict, rights: str = "", cutoff: int = 1930) -> tuple[bool, str]:
    """Hold back anything that may still be under copyright: the GitHub library is public."""
    if isinstance(rights, dict) or rights is None:            # older callers passed the loc.gov item JSON
        it = (rights or {}).get("item") or {}
        rights = " ".join(L.as_text(it.get(k)) for k in ("rights_advisory", "rights", "rights_information")) + " " + L.as_text((rights or {}).get("rights"))
    years = [int(y) for y in YEAR.findall(meta.get("date", ""))]
    if years and min(years) < cutoff:
        return True, f"published {min(years)}"
    if OPEN.search(rights or ""):
        return True, "open rights statement"
    return False, "date after %d and no open-rights statement" % cutoff


# ------------------------------------------------------------------------------------------- the run
class Absorber:
    def __init__(self, store, fetcher=None, log=print, progress=None, stop: threading.Event | None = None,
                 rights_gate: bool = True, per_page: int = 25, store_for=None):
        self.store, self.log, self.store_for = store, log, store_for
        self.fetcher = fetcher or L.Fetcher(slow=90)
        self.progress = progress or (lambda done, total, label: None)
        self.stop = stop or threading.Event()
        self.rights_gate, self.per_page = rights_gate, per_page

    def run(self, sources: list, max_items: int, max_pages: int = 20) -> dict:
        """sources: loc.gov source strings, or dicts {"src", "section", "title", "store"} to file them in a section."""
        lib = Library(self.store, self.log, self.store_for)
        start = dict(lib.state["totals"])
        got, held, empty = 0, 0, 0
        last_sha = None
        for spec in sources:
            spec = spec if isinstance(spec, dict) else {"src": spec}
            src = spec["src"]
            sec = lib.section(spec.get("section") or "general", spec.get("title", ""), spec.get("store") or "core")
            sec_id = [k for k, v in lib.state["sections"].items() if v is sec][0]
            if self.stop.is_set() or got >= max_items:
                break
            ad = AR.adapter_for(src, self.fetcher, self.per_page)
            prog = lib.state["sources"].setdefault(src, {"next": ad.start_url(src), "pages": 0, "done": False})
            if prog.get("done"):
                self.log(f"{AR.describe(src)}: already fully absorbed")
                continue
            url, pages = prog["next"], 0
            self.log(f"{AR.describe(src)}: catalogue page {prog['pages'] + 1}")
            while url and got < max_items and pages < max_pages and not self.stop.is_set():
                results, nxt = ad.page(url)
                if results is None:
                    self.log(f"  {ad.name} did not answer for {url} — try again later (place kept)")
                    break
                page_complete = True
                for rec in results:
                    if self.stop.is_set() or got >= max_items:
                        page_complete = False
                        break
                    rid = L.as_text(rec.get("id") or rec.get("url")) if ad.name == "loc.gov" else f"https://archive.org/details/{rec.get('identifier')}"
                    if not rid or lib.seen(rid):
                        continue
                    it = ad.item(rec)
                    if not it:
                        continue
                    meta = {"title": it["title"], "date": it["date"], "url": it["url"], "source": src, "section": sec_id,
                            "archive": ad.name, "format": it["format"]}
                    if it.get("thumb"):
                        meta["thumb"] = it["thumb"]
                    if it.get("media"):
                        meta["media"] = it["media"]
                    if self.rights_gate:
                        ok, why = rights_ok(meta, it.get("rights", ""))
                        if not ok:
                            lib.mark(it["id"], "-held")
                            held += 1
                            self.log(f"  held back ({why}): {meta['title'][:70]}")
                            continue
                    text, kind = ad.text(it), "fulltext"
                    if len(text) < MIN_TEXT:                     # recordings: captions are the transcript
                        cap = next((m for m in it.get("media") or [] if m["type"] == "caption"), None)
                        raw = self.fetcher.get_bytes(cap["url"]) if cap else None
                        if isinstance(raw, (bytes, bytearray)):
                            text, kind = AR.captions_to_text(raw), "captions"
                    if len(text) < MIN_TEXT and it.get("media") and len(it.get("catalogue", "")) >= AR.MIN_MEDIA_TEXT:
                        text, kind = it["catalogue"], "catalogue"   # a film or photo with no transcript: keep its record
                    if len(text) < (MIN_TEXT if kind == "fulltext" else AR.MIN_MEDIA_TEXT):
                        lib.mark(it["id"], "-")
                        empty += 1
                        self.log(f"  no text or media online: {meta['title'][:70]}")
                        continue
                    meta["text_from"] = kind
                    before = lib.state["totals"]["meanings"]
                    n = lib.add_doc(it["id"], meta, text, sec_id)
                    got += 1
                    media = f" · {len(it['media'])} media link(s)" if it.get("media") else ""
                    self.log(f"  [{got}/{max_items}] {meta['format']} · {n:,} sentences ({kind}){media} · +{lib.state['totals']['meanings'] - before:,} new meanings · {meta['title'][:60]}")
                    self.progress(got, max_items, meta["title"])
                    del text
                    if lib.pending >= COMMIT_EVERY:
                        last_sha = lib.flush(f"COG absorb: +{got} items from {ad.name} ({src})")
                        self.log(f"  pushed to GitHub {str(last_sha)[:7]}")
                if page_complete:
                    pages += 1
                    prog["pages"] += 1
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
        if p.startswith("books/core-m-"):
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
    d = json.loads(store.files["sections/general/docs-0001.json"])["docs"]
    seqA = d[0]["seq"]
    first = seqA.split()[:3]
    assert first == ["1000.0", "1000.1", "1000.2"], first           # same meaning, three exact wordings
    assert "|" in seqA
    back = decode(store, seqA)
    assert back.startswith("Congress shall have power to lay and collect taxes. The power to lay and collect taxes, Congress shall have."), back[:80]
    assert "It is so ordered." in back
    m = json.loads(store.files["books/core-m-0001.json"])
    assert m["s"][0][:3] == [1000, ["congress", "power", "lay", "collect", "taxes"], [0]], m["s"][0]
    cat = json.loads(store.files["books/catalog.json"])
    assert any(b["file"] == "books/core-m-0001.json" and b["from"] == 1000 for b in cat["books"])
    # second run: nothing new, addresses never change, the doc is not re-absorbed
    before = dict(store.files)
    r2 = Absorber(store, FakeFetcher(), log=logs.append).run(["q:test"], max_items=10)
    assert r2["docs"] == 0 and store.files["books/core-m-0001.json"] == before["books/core-m-0001.json"]
    # a new wording of a known meaning in a later run continues the variant numbers (append-only)
    pages["https://www.loc.gov/search/?q=more&fo=json&c=25&sp=1"] = {"pagination": {}, "results": [{"id": "http://www.loc.gov/item/e/", "title": "E", "date": "1700"}]}
    texts["e"] = "Taxes: Congress shall have power to lay and collect them. " * 10 + "To lay and collect taxes, Congress shall have power."
    lib = Library(store, log=logs.append)
    nv = lib.nvar[1000]
    Absorber(store, FakeFetcher(), log=logs.append).run(["q:more"], max_items=5)
    lib2 = Library(store, log=logs.append)
    assert lib2.nvar[1000] == nv + 1, (nv, lib2.nvar[1000])
    e_seq = [x for x in json.loads(store.files["sections/general/docs-0001.json"])["docs"] if x["title"] == "E"][0]["seq"]
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
    packs = [p for p in store.files if p.startswith("books/core-m-")]
    assert len(packs) > 3, packs
    f_seq = " ".join(x["seq"] for x in json.loads(store.files[max(p for p in store.files if p.startswith("sections/general/docs-"))])["docs"] if x["title"] == "F")
    assert decode(store, f_seq).startswith("Sentence number 0 about subject 0. Sentence number 1"), decode(store, f_seq)[:60]
    # sections: groups with their own storage; meaning-ids stay global
    side = {}
    factory = lambda repo: side.setdefault(repo, MemStore())
    pages["https://www.loc.gov/collections/law-test/?fo=json&c=25&sp=1"] = {"pagination": {}, "results": [{"id": "http://www.loc.gov/item/g/", "title": "G", "date": "1791"}]}
    pages["https://www.loc.gov/search/?q=ref&fo=json&c=25&sp=1"] = {"pagination": {}, "results": [{"id": "http://www.loc.gov/item/h/", "title": "H", "date": "1644"}]}
    texts["g"] = "It is so ordered. Congress shall make no law respecting an establishment of religion. " * 5
    texts["h"] = "It is so ordered. Lex rex: the law is king. A brand new reformer sentence here. " * 5
    Absorber(store, FakeFetcher(), log=logs.append, store_for=factory).run(
        [{"src": "law-test", "section": "Law", "title": "Law"},
         {"src": "q:ref", "section": "reformers", "title": "The Reformers", "store": "PxD2/cog-reformers"}], max_items=5)
    assert "sections/law/docs-0001.json" in store.files                      # core-hosted section
    assert "sections/reformers/docs-0001.json" in side["PxD2/cog-reformers"].files   # its own repo
    h = json.loads(side["PxD2/cog-reformers"].files["sections/reformers/docs-0001.json"])["docs"][0]["seq"]
    g = json.loads(store.files["sections/law/docs-0001.json"])["docs"][0]["seq"]
    assert h.split()[0] == g.split()[0], (h[:20], g[:20])                    # "It is so ordered." = same address everywhere
    assert decode(store, h).startswith("It is so ordered. Lex rex")
    assert not any(p.startswith("sections/reformers/docs") for p in store.files)       # documents in their own repo
    assert "sections/reformers/index-0001.json" in store.files                          # the finder index stays in core
    ix = json.loads(store.files["sections/law/index-0001.json"])["e"][0]
    assert ix["t"] == "G" and ix["y"] == 1791 and ix["f"] == 1 and ix["i"] == 0, ix
    # an article: levels + quiz, same global numbers
    lib = Library(store, log=logs.append, store_for=factory)
    lib.add_article("article:test@1", "encyclopedia", {"id": "article:test", "title": "Test", "subject": "Civics", "year": 1791,
                    "texts": {"young": "It is so ordered. Kids text here.", "deeper": "It is so ordered. Older text here."},
                    "quiz": [{"level": "young", "q": "?", "choices": ["a", "b"], "answer": 1}]})
    lib.flush("article")
    art = json.loads(store.files["sections/encyclopedia/docs-0001.json"])["docs"][0]
    assert art["levels"]["young"].split()[0] == g.split()[0] and art["quiz"][0]["answer"] == 1
    cat = json.loads(store.files["books/catalog.json"])
    secs = {x["id"]: x for x in cat["sections"]}
    assert secs["reformers"]["base"].startswith("https://raw.githubusercontent.com/PxD2/cog-reformers/") and secs["law"]["base"] == ""
    # recordings and other archives: captions become the transcript, media stays as links
    av = {
        "https://www.loc.gov/film-and-videos/?q=edison&fo=json&c=25&sp=1": {"pagination": {}, "results": [
            {"id": "http://www.loc.gov/item/v1/", "title": "Edison film", "date": "1899", "original_format": ["film, video"],
             "image_url": ["https://tile.loc.gov/image-services/iiif/v1/full/pct:25/0/default.jpg"]},
            {"id": "http://www.loc.gov/item/p1/", "title": "Photo of a mill", "date": "1885", "original_format": ["photo, print, drawing"],
             "description": ["A stone grist mill on the river, photographed from the east bank in autumn."]}]},
        "https://www.loc.gov/item/v1/?fo=json": {"item": {}, "resources": [{"video": "https://tile.loc.gov/v1/v1.mp4",
             "files": [[{"mimetype": "text/vtt", "url": "https://tile.loc.gov/v1/v1.vtt"}]]}]},
        "https://www.loc.gov/item/p1/?fo=json": {"item": {"summary": "A stone grist mill on the river, photographed from the east bank in autumn."},
             "resources": [{"image": "https://tile.loc.gov/image-services/iiif/p1/full/pct:50/0/default.jpg"}]},
        "https://archive.org/advancedsearch.php?q=%28prelinger%29%20AND%20mediatype%3A%28movies%29&fl[]=identifier&fl[]=title&fl[]=date&fl[]=year&fl[]=mediatype&fl[]=licenseurl&rows=25&page=1&output=json":
            {"response": {"numFound": 2, "docs": [{"identifier": "oldfilm", "title": "Old Film", "mediatype": "movies", "year": "1952"},
                                                   {"identifier": "newfilm", "title": "New Film", "mediatype": "movies", "year": "2005"}]}},
        "https://archive.org/metadata/oldfilm": {"metadata": {"title": "Old Film", "mediatype": "movies", "year": "1952",
             "licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/", "description": "A civil defense film."},
             "files": [{"name": "oldfilm.mp4", "format": "h.264"}, {"name": "oldfilm.srt", "format": "SubRip"}]},
        "https://archive.org/metadata/newfilm": {"metadata": {"title": "New Film", "mediatype": "movies", "year": "2005"}, "files": []},
    }
    blobs = {"https://tile.loc.gov/v1/v1.vtt": b"WEBVTT\n\n00:00.000 --> 00:02.000\nThe train arrives at the station.\n\n00:02.000 --> 00:04.000\nThe train arrives at the station.\nPeople step down to the platform.\n",
             "https://archive.org/download/oldfilm/oldfilm.srt": b"1\n00:00:01,000 --> 00:00:03,000\nDuck and cover, children.\n\n2\n00:00:03,000 --> 00:00:05,000\nThis film shows how to stay safe.\n"}

    class AVFetcher:
        def get_json(self, url):
            return av.get(url)

        def get_bytes(self, url):
            return blobs.get(url)

    st2 = MemStore()
    r = Absorber(st2, AVFetcher(), log=logs.append).run(
        [{"src": "q:edison |fmt:film-and-videos", "section": "film", "title": "Film & Sound"},
         {"src": "ia:prelinger |fmt:movies", "section": "film", "title": "Film & Sound"}], max_items=10)
    assert r["docs"] == 3 and r["held_back"] == 1, (r, logs[-6:])
    docs = json.loads(st2.files["sections/film/docs-0001.json"])["docs"]
    v = docs[0]
    assert v["format"] == "video" and v["text_from"] == "captions" and any(m["type"] == "video" for m in v["media"]), v
    assert decode(st2, v["seq"]) == "The train arrives at the station. People step down to the platform."
    ph = docs[1]
    assert ph["format"] == "image" and ph["text_from"] == "catalogue" and ph["media"][0]["type"] == "image"
    ia = docs[2]
    assert ia["archive"] == "Internet Archive" and ia["text_from"] == "captions" and ia["media"][0]["url"].endswith("oldfilm.mp4")
    ix = json.loads(st2.files["sections/film/index-0001.json"])["e"]
    assert ix[0]["fm"] == "video" and ix[0]["mv"] == 1 and ix[1]["fm"] == "image"
    print(f"selftest ok · {len(store.commits)} commits · {len(packs)} meaning packs · next meaning {json.loads(store.files['loc/state.json'])['next_meaning']}")


# ------------------------------------------------------------------------------------------- command line
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", action="append", default=[], help="loc.gov search words (repeatable)")
    ap.add_argument("--collection", action="append", default=[], help="loc.gov collection slug (repeatable)")
    ap.add_argument("--books", action="store_true", help="searches: books / printed text only")
    ap.add_argument("--format", default="", help="loc.gov: books film-and-videos audio photos maps manuscripts newspapers · "
                                                 "Internet Archive: movies audio texts image")
    ap.add_argument("--ia", action="append", default=[], help="Internet Archive search words (repeatable)")
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
    fmt = "books" if a.books and not a.format else a.format
    sources = ([AR.make_src("loc", "query", q, fmt) for q in a.query] + list(a.collection)
               + [AR.make_src("ia", "query", q, fmt) for q in a.ia])
    if not sources:
        ap.error("give at least one --query, --collection or --ia")
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
