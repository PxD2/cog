#!/usr/bin/env python3
"""Library Desk — a small internal agent that helps with every COG library job, on base1's own models (Ollama).

It can look things up, find material on loc.gov, set up sections and sources, read documents back from their
addresses, check the run log, and prepare an absorb. It never pushes to GitHub by itself: an absorb is proposed and
only runs when you press "Run it" in the window.

The Library of Congress is a taxpayer trust: held in trust for the people who paid for it, not a government organization or entity.

    python library_desk.py "what's in the library?"        # one question from the command line
    python library_desk.py --selftest                       # offline test (fake model, fake GitHub)

Works without a model too: simple requests ("status", "meaning 1042", "find Lex Rex", "log") are answered directly.
Standard library only.
"""
from __future__ import annotations

import json, re, sys, threading, urllib.request
from pathlib import Path
from urllib.parse import quote_plus

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cog_absorber as A        # noqa: E402
import archives as AR           # noqa: E402

OLLAMA = "http://127.0.0.1:11434"
PREFERRED = ["gpt-oss:20b", "qwen3.6:27b", "qwen2.5:14b", "hermes3:8b", "llama3.1:latest", "llama3.2:latest", "mistral:latest"]
MAX_STEPS = 6

SYSTEM = f"""You are the Library Desk inside PXD2's COG Absorber on base1. You help Chad run his COG library: a permanent,
append-only library of meanings on GitHub (PxD2/cog). Every distinct meaning has one global meaning-id (absorbed ones from
1000); every exact sentence under it has a variant index. The address (meaning-id, variant-index) is written "1042.3".
Documents are held in library sections (groups); each section is stored in core (PxD2/cog) or its own repo.
Sources: Library of Congress and the Internet Archive, any format. Video, audio and photos are kept as their catalogue
text, captions/transcripts (as COG) plus links to play them at the archive — the recordings themselves are never copied.
{A.TRUST}
Rules:
- Use the tools to check facts; never invent meaning-ids, counts, or loc.gov items.
- You cannot push anything. To absorb, call propose_absorb; Chad presses Run it to start it.
- Keep answers short and direct. Chad writes in quick shorthand; answer the same way. No filler."""


# ------------------------------------------------------------------------------------------- read side
class Reader:
    """Read-only view of the library on GitHub (cached for the session)."""

    def __init__(self, store=None, store_for=None):
        self.store = store or A.GitHubStore()
        self.store_for = store_for or (lambda repo: A.GitHubStore(repo, getattr(self.store, "branch", A.BRANCH),
                                                                  getattr(self.store, "token", None)))
        self._loaded = False
        self._files: dict[str, object] = {}
        self._reg = None

    def _ensure(self):
        if not self._loaded:
            self.store.refresh()
            self._loaded = True

    def refresh(self):
        self._loaded, self._files, self._reg = False, {}, None

    def json(self, path: str, repo: str = "core"):
        key = repo + ":" + path
        if key not in self._files:
            self._ensure()
            if repo == "core":
                b = self.store.get(path)
            else:
                s = self.store_for(repo)
                s.refresh()
                b = s.get(path)
            self._files[key] = json.loads(b) if b else None
        return self._files[key]

    def state(self) -> dict:
        return self.json("loc/state.json") or {"next_meaning": A.FIRST_ABSORBED, "totals": {}, "sections": {}, "sources": {}}

    def catalog(self) -> dict:
        return self.json("books/catalog.json") or {"books": [], "sections": []}

    def rows(self, m: int) -> list[tuple[int, list[str], list[str]]]:
        out = []
        for b in self.catalog().get("books", []):
            if b.get("kind") != "meanings":
                continue
            if b.get("room") == "core" and not ((b.get("from") is not None and b["from"] <= m <= b["to"]) or m in (b.get("cont") or [])):
                continue
            pack = self.json(b["file"]) or {}
            for r in pack.get("s", []):
                if r[0] == m:
                    out.append((r[2][0], r[1], r[3]))
        return sorted(out, key=lambda x: x[0])

    def variant(self, m: int, v: int) -> str | None:
        for start, _, vs in self.rows(m):
            if start <= v < start + len(vs):
                return vs[v - start]
        return None

    def registry(self) -> tuple[dict, dict]:
        if self._reg is None:
            self._ensure()
            mean, var = {}, {}
            for p in sorted(x for x in self.store.tree if x.startswith("loc/registry/r-")):
                seg = self.json(p) or {}
                mean.update(seg.get("m", {}))
                var.update(seg.get("v", {}))
            self._reg = (mean, var)
        return self._reg

    def decode(self, seq: str, limit: int = 4000) -> str:
        out, para, size = [], [], 0
        for tok in seq.split():
            if tok == "|":
                out.append(" ".join(para)); para = []
                continue
            m, v = map(int, tok.split("."))
            t = self.variant(m, v) or f"[{tok}]"
            para.append(t)
            size += len(t) + 1
            if size > limit:
                para.append("…")
                break
        out.append(" ".join(para))
        return "\n\n".join(x for x in out if x)

    def documents(self, section: str | None = None):
        for sec in self.catalog().get("sections", []):
            if section and section.lower() not in (sec["id"], sec["title"].lower()):
                continue
            for f in sec.get("files", []):
                pack = self.json(f, sec.get("store", "core")) or {}
                for d in pack.get("docs", []):
                    yield sec, d


# ------------------------------------------------------------------------------------------- the desk
class Desk:
    """hooks (from the window): sources() -> list, add_source(kind, value, section) -> str,
    new_section(title, store) -> str, propose(dict) -> str, log_tail(n) -> str, sections() -> dict"""

    def __init__(self, reader: Reader | None = None, hooks: dict | None = None, chat=None, fetcher=None, model: str = ""):
        self.reader = reader or Reader()
        self.h = hooks or {}
        self._chat = chat or self._ollama_chat
        self.fetcher = fetcher
        self.model = model
        self.history: list[dict] = []
        self.stop = threading.Event()
        self.tools = self._tool_specs()

    # ---- models
    @staticmethod
    def models() -> list[str]:
        try:
            with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=4) as r:
                names = [m["name"] for m in json.loads(r.read()).get("models", [])]
        except Exception:
            return []
        names = [n for n in names if "embed" not in n]
        return sorted(names, key=lambda n: (PREFERRED.index(n) if n in PREFERRED else 99, n))

    def _ollama_chat(self, messages: list[dict], tools: list[dict]) -> dict:
        body = json.dumps({"model": self.model, "messages": messages, "tools": tools, "stream": False,
                           "options": {"temperature": 0.2, "num_ctx": 16384}}).encode()
        req = urllib.request.Request(OLLAMA + "/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())["message"]

    # ---- tools
    def _tool_specs(self) -> list[dict]:
        def t(name, desc, props=None, req=None):
            return {"type": "function", "function": {"name": name, "description": desc,
                    "parameters": {"type": "object", "properties": props or {}, "required": req or []}}}
        S = {"type": "string"}
        I = {"type": "integer"}
        return [
            t("library_status", "Totals, next free meaning-id, sections with counts and storage, where each source left off."),
            t("list_sources", "The loc.gov sources set up in the window, which section each goes to, and which are ticked."),
            t("lookup_meaning", "Every exact sentence stored under a meaning-id, or one address like 1042.3.", {"address": S}, ["address"]),
            t("find_sentence", "Find the address of an exact sentence, or other sentences with the same meaning.", {"sentence": S}, ["sentence"]),
            t("list_documents", "Documents already absorbed, optionally only one section, optionally filtered by words in the title.",
              {"section": S, "title_contains": S}),
            t("read_document", "Read an absorbed document back from its addresses (first part).", {"title_contains": S}, ["title_contains"]),
            t("search_loc", "Search loc.gov for items (title, date, formats online). Read-only. format: books, film-and-videos, audio, photos, maps, manuscripts, newspapers.",
              {"query": S, "format": S, "books_only": {"type": "boolean"}}, ["query"]),
            t("search_internet_archive", "Search the Internet Archive (public domain / open licence first). Read-only. format: movies, audio, texts, image.",
              {"query": S, "format": S}, ["query"]),
            t("find_collections", "Find loc.gov collections (slugs) matching words. Read-only.", {"words": S}, ["words"]),
            t("new_section", "Create a library section. store = 'core' or 'owner/repo'.", {"title": S, "store": S}, ["title"]),
            t("add_source", "Add a source to the window. archive = 'loc' or 'ia'; kind = 'query' or 'collection' (loc only); "
              "format optional (loc: books, film-and-videos, audio, photos, maps, manuscripts, newspapers; ia: movies, audio, texts, image); section = section id or title.",
              {"archive": S, "kind": S, "value": S, "format": S, "section": S}, ["kind", "value", "section"]),
            t("propose_absorb", "Prepare an absorb run for Chad to approve with the Run it button. Nothing runs until he does.",
              {"sources": {"type": "array", "items": S, "description": "source values (search words or collection slugs) already in the window"},
               "documents": I, "dry_run": {"type": "boolean"}}, ["sources", "documents"]),
            t("read_log", "Last lines of the absorber run log.", {"lines": I}),
        ]

    def call(self, name: str, args: dict) -> str:
        try:
            fn = getattr(self, "t_" + name)
        except AttributeError:
            return f"unknown tool {name}"
        try:
            out = fn(**(args or {}))
        except TypeError as e:
            return f"bad arguments for {name}: {e}"
        except Exception as e:      # noqa: BLE001
            return f"{name} failed: {type(e).__name__}: {e}"
        s = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        return s[:6000]

    def t_library_status(self):
        st = self.reader.state()
        secs = {k: {"title": v["title"], "store": v["store"], "documents": v.get("docs", 0), "sentences": v.get("sentences", 0)}
                for k, v in (st.get("sections") or {}).items()}
        src = {(k[2:].replace(A.L.BOOKS_TAG, "") if k.startswith("q:") else k): ("complete" if v.get("done") else f"{v.get('pages', 0)} pages in")
               for k, v in (st.get("sources") or {}).items()}
        return {"next_free_meaning_id": st.get("next_meaning"), "totals": st.get("totals"), "sections": secs, "sources": src,
                "updated": st.get("updated")}

    def t_list_sources(self):
        return self.h["sources"]() if "sources" in self.h else "the window is not attached"

    def t_lookup_meaning(self, address: str):
        m = re.fullmatch(r"\s*\(?(\d+)\s*(?:[.,]\s*(\d+))?\)?\s*", str(address))
        if not m:
            return "give a meaning-id like 1042 or an address like 1042.3"
        mid = int(m.group(1))
        rows = self.reader.rows(mid)
        if not rows:
            return f"no meaning {mid} yet (next free is {self.reader.state().get('next_meaning')})"
        keys = next((k for _, k, _ in rows if k), [])
        variants = [(s + i, v) for s, _, vs in rows for i, v in enumerate(vs)]
        if m.group(2) is not None:
            v = int(m.group(2))
            hit = [t for i, t in variants if i == v]
            return {"address": f"{mid}.{v}", "sentence": hit[0] if hit else None, "keys": keys}
        return {"meaning": mid, "keys": keys, "variants": [f"{mid}.{i}  {t}" for i, t in variants[:40]],
                "count": len(variants)}

    def t_find_sentence(self, sentence: str):
        mean, var = self.reader.registry()
        s = A.norm_sentence(sentence)
        exact = var.get(A.h16(s))
        m = mean.get(A.h16(A.meaning_sig(s)))
        if exact:
            return {"exact_address": exact, "sentence": s}
        if m is not None:
            return {"exact_address": None, "same_meaning": m, "known_wordings": self.t_lookup_meaning(str(m)).get("variants", [])[:10]}
        return "not in the library yet (no exact match, no sentence with the same meaning)"

    def t_list_documents(self, section: str = "", title_contains: str = ""):
        out = []
        for sec, d in self.reader.documents(section or None):
            if title_contains and title_contains.lower() not in d.get("title", "").lower():
                continue
            out.append(f"[{sec['title']}] {d.get('title', '')[:90]} ({d.get('date', '')}) · {d.get('n', 0)} sentences")
            if len(out) >= 40:
                out.append("… more")
                break
        return out or "no documents found"

    def t_read_document(self, title_contains: str):
        for sec, d in self.reader.documents():
            if title_contains.lower() in d.get("title", "").lower():
                return {"section": sec["title"], "title": d["title"], "date": d.get("date"), "loc_url": d.get("url"),
                        "first_addresses": " ".join(d["seq"].split()[:12]), "text": self.reader.decode(d["seq"], 2500)}
        return "no absorbed document has that in its title"

    def _get(self, url):
        f = self.fetcher or A.L.Fetcher(slow=60)
        self.fetcher = f
        return f.get_json(url)

    def t_search_loc(self, query: str, format: str = "", books_only: bool = False):
        fmt = "books" if books_only and not format else format
        data = self._get(AR.LOC(None, 10).start_url(AR.make_src("loc", "query", query, fmt if fmt in AR.LOC_FORMATS else "")))
        if not isinstance(data, dict):
            return "loc.gov did not answer — try again in a minute"
        out = []
        for r in (data.get("results") or [])[:10]:
            fmt = A.L.as_text(r.get("online_format") or r.get("online-format"))
            out.append({"title": A.L.as_text(r.get("title"))[:120], "date": A.L.as_text(r.get("date"))[:20],
                        "online": fmt[:60], "id": A.L.as_text(r.get("id"))})
        return {"query": query, "format": fmt, "total": (data.get("pagination") or {}).get("of"), "results": out}

    def t_search_internet_archive(self, query: str, format: str = ""):
        url = AR.IA(None).start_url(AR.make_src("ia", "query", query, format if format in AR.IA_FORMATS else ""))
        data = self._get(url.replace("rows=25", "rows=10"))
        if not isinstance(data, dict):
            return "archive.org did not answer — try again in a minute"
        docs = (data.get("response") or {}).get("docs") or []
        return {"query": query, "total": (data.get("response") or {}).get("numFound"),
                "results": [{"id": d.get("identifier"), "title": A.L.as_text(d.get("title"))[:120], "year": d.get("year") or d.get("date"),
                             "type": d.get("mediatype"), "open_licence": bool(d.get("licenseurl"))} for d in docs[:10]]}

    def t_find_collections(self, words: str):
        data = self._get(f"{A.L.BASE}/collections/?q={quote_plus(words)}&fo=json&c=15")
        if not isinstance(data, dict):
            return "loc.gov did not answer — try again in a minute"
        out = []
        for r in (data.get("results") or [])[:15]:
            url = A.L.as_text(r.get("url") or r.get("id"))
            m = re.search(r"/collections/([^/?#]+)", url)
            out.append({"slug": m.group(1) if m else url, "title": A.L.as_text(r.get("title"))[:120],
                        "items": r.get("items") or r.get("count")})
        return out or "no collections matched"

    def t_new_section(self, title: str, store: str = "core"):
        return self.h["new_section"](title, store or "core") if "new_section" in self.h else "the window is not attached"

    def t_add_source(self, kind: str, value: str, section: str, archive: str = "loc", format: str = ""):
        if kind not in ("query", "collection"):
            return "kind must be query or collection"
        return self.h["add_source"](kind, value, section, archive, format) if "add_source" in self.h else "the window is not attached"

    def t_propose_absorb(self, sources: list, documents: int = 10, dry_run: bool = False):
        plan = {"sources": [str(x) for x in sources], "documents": max(1, min(int(documents), 500)), "dry_run": bool(dry_run)}
        return self.h["propose"](plan) if "propose" in self.h else "the window is not attached"

    def t_read_log(self, lines: int = 40):
        return self.h["log_tail"](int(lines)) if "log_tail" in self.h else "no log"

    # ---- talking
    def quick(self, text: str) -> str | None:
        """Answers that need no model."""
        t = text.strip().lower()
        if t in ("status", "stats", "what's in the library", "whats in the library", "what's in the library?"):
            return json.dumps(self.t_library_status(), indent=1)
        m = re.fullmatch(r"(?:meaning|lookup|look up|address)?\s*(\d+(?:\.\d+)?)", t)
        if m:
            r = self.t_lookup_meaning(m.group(1))
            return r if isinstance(r, str) else json.dumps(r, indent=1, ensure_ascii=False)
        if t in ("log", "show log", "read log"):
            return self.t_read_log(40)
        return None

    def ask(self, text: str, on_step=lambda s: None) -> str:
        if not self.model:
            q = self.quick(text)
            return q if q is not None else ("No local model is running. Start Ollama on base1 (ollama serve), "
                                            "or ask: status · 1042 · 1042.3 · log")
        self.history.append({"role": "user", "content": text})
        msgs = [{"role": "system", "content": SYSTEM}] + self.history[-16:]
        for _ in range(MAX_STEPS):
            if self.stop.is_set():
                return "stopped"
            msg = self._chat(msgs, self.tools)
            calls = msg.get("tool_calls") or []
            msgs.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": calls} if calls else
                        {"role": "assistant", "content": msg.get("content", "")})
            if not calls:
                answer = (msg.get("content") or "").strip()
                self.history.append({"role": "assistant", "content": answer})
                return answer or "(no answer)"
            for c in calls:
                fn = c.get("function", {})
                name, args = fn.get("name", ""), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                on_step(f"→ {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
                result = self.call(name, args)
                msgs.append({"role": "tool", "content": result, "tool_name": name})
        answer = "I hit the step limit; here is where I got to. Ask me to keep going."
        self.history.append({"role": "assistant", "content": answer})
        return answer


# ------------------------------------------------------------------------------------------- self-test
def selftest() -> None:
    store = A.MemStore()

    class FakeFetcher:
        def get_json(self, url):
            if "/search/?q=test" in url:
                return {"pagination": {}, "results": [{"id": "http://www.loc.gov/item/a/", "title": "Lex Rex", "date": "1644"}]}
            if "/collections/?q=" in url:
                return {"results": [{"url": "https://www.loc.gov/collections/federalist-papers/", "title": "The Federalist Papers", "items": 85}]}
            return {"item": {}, "resources": [{"files": [[{"mimetype": "text/plain", "url": "https://tile.loc.gov/a.txt"}]]}]}

        def get_bytes(self, url):
            return ("A law against tyrants is no law. Lex rex: the law is king.\n\n" * 6).encode()

    A.Absorber(store, FakeFetcher(), log=lambda *a: None).run([{"src": "q:test", "section": "reformers", "title": "The Reformers"}], 3)
    reader = Reader(store)
    added, proposed = [], []
    hooks = {"sources": lambda: [{"value": "test", "section": "reformers", "on": True}],
             "add_source": lambda k, v, s, a="loc", f="": (added.append((k, v, s)), f"added {v} to {s}")[1],
             "new_section": lambda t, s: f"section {t} in {s}",
             "propose": lambda plan: (proposed.append(plan), "proposed — waiting for Chad to press Run it")[1],
             "log_tail": lambda n: "last line"}
    # a scripted model: calls tools, then answers
    script = [
        {"tool_calls": [{"function": {"name": "find_sentence", "arguments": {"sentence": "Lex rex:  the law is king."}}}]},
        {"tool_calls": [{"function": {"name": "find_collections", "arguments": {"words": "federalist"}}},
                        {"function": {"name": "add_source", "arguments": {"kind": "collection", "value": "federalist-papers", "section": "law"}}},
                        {"function": {"name": "propose_absorb", "arguments": {"sources": ["federalist-papers"], "documents": 5}}}]},
        {"content": "Lex Rex line is 1001.0. Federalist Papers added to Law; absorb of 5 is waiting for you."},
    ]
    seen = []

    def chat(msgs, tools):
        seen.append([m for m in msgs if m["role"] == "tool"])
        return script.pop(0)

    d = Desk(reader, hooks, chat=chat, fetcher=FakeFetcher(), model="fake")
    steps = []
    ans = d.ask("where's lex rex, and set up the federalist papers", steps.append)
    assert ans.startswith("Lex Rex line is"), ans
    tool_out = [m["content"] for m in seen[1]]
    assert json.loads(tool_out[0])["exact_address"] == "1001.0", tool_out[0]
    assert added == [("collection", "federalist-papers", "law")] and proposed[0]["documents"] == 5
    assert len(steps) == 4
    # no model: quick answers
    d2 = Desk(reader, hooks, model="")
    assert json.loads(d2.ask("1000"))["meaning"] == 1000
    assert json.loads(d2.ask("1001.0"))["sentence"] == "Lex rex: the law is king."
    assert "next_free_meaning_id" in d2.ask("status")
    assert "Lex rex" in d.call("read_document", {"title_contains": "lex"})
    assert "[The Reformers]" in d.call("list_documents", {})
    print("desk selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif len(sys.argv) > 1:
        ms = Desk.models()
        d = Desk(model=ms[0] if ms else "")
        print(d.ask(" ".join(sys.argv[1:]), on_step=print))
    else:
        print(__doc__)
