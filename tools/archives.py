#!/usr/bin/env python3
"""Archive adapters for the COG absorber: where items come from, and how their text and media are found.

Every adapter turns a source string into catalogue pages, and each catalogue record into one item:
    title, date, link, format (video | audio | image | map | manuscript | newspaper | book | text),
    text (full text, transcript or captions, else the catalogue description) -> stored as COG addresses,
    media (streaming / image / caption links)                                 -> stored as links, never copied.

GitHub rejects files over 100 MB, and the library must stay small, so recordings, photographs and scans stay at the
archive; the library keeps their catalogue text, transcripts and captions (as COG) and the links that play them.

Sources:
    Library of Congress   "q:<words>"  "q:<words> |books"  "q:<words> |fmt:film-and-videos"   or a collection slug
                          formats: books, film-and-videos, audio, photos, maps, manuscripts, newspapers
    Internet Archive      "ia:<words>"  "ia:<words> |fmt:movies"   formats: movies, audio, texts, image
The Library of Congress is a taxpayer trust: held in trust for the people who paid for it, not a government organization or entity.
"""
from __future__ import annotations

import json, re
from urllib.parse import quote, quote_plus

import loc_loader as L

LOC_FORMATS = {"books": "Books", "film-and-videos": "Video", "audio": "Audio", "photos": "Photos", "maps": "Maps",
               "manuscripts": "Manuscripts", "newspapers": "Newspapers"}
IA_FORMATS = {"movies": "Video", "audio": "Audio", "texts": "Books", "image": "Images"}
VIDEO = re.compile(r"\.(mp4|m4v|webm|mov|ogv)(\?|$)", re.I)
AUDIO = re.compile(r"\.(mp3|m4a|wav|ogg|oga|flac|aac)(\?|$)", re.I)
IMAGE = re.compile(r"\.(jpe?g|png|gif|webp)(\?|$)", re.I)
CAPTION = re.compile(r"\.(vtt|srt)(\?|$)", re.I)
MAX_MEDIA = 12
MIN_MEDIA_TEXT = 40


def split_src(src: str) -> tuple[str, str, str]:
    """-> (archive, query-or-slug, format)"""
    arch = "ia" if src.startswith("ia:") else "loc"
    body = src[3:] if arch == "ia" else src
    fmt = ""
    m = re.search(r"\s\|fmt:([\w-]+)$", body)
    if m:
        fmt, body = m.group(1), body[: m.start()]
    elif body.endswith(L.BOOKS_TAG):
        fmt, body = "books", body[: -len(L.BOOKS_TAG)]
    return arch, body, fmt


def make_src(archive: str, kind: str, value: str, fmt: str = "") -> str:
    if archive == "ia":
        return "ia:" + value + (f" |fmt:{fmt}" if fmt else "")
    if kind == "collection":
        return value
    if fmt == "books":
        return "q:" + value + L.BOOKS_TAG          # same key as earlier runs, so their place is kept
    return "q:" + value + (f" |fmt:{fmt}" if fmt else "")


def describe(src: str) -> str:
    arch, body, fmt = split_src(src)
    name = body[2:] if body.startswith("q:") else body
    f = (IA_FORMATS if arch == "ia" else LOC_FORMATS).get(fmt, "")
    return f"{'Internet Archive' if arch == 'ia' else 'loc.gov'} · {name}" + (f" · {f}" if f else "")


# ------------------------------------------------------------------ media helpers
def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def collect_media(*jsons) -> list[dict]:
    """Every playable / viewable link in the records: [{type, url, mime?}], best first, deduplicated."""
    found: dict[str, dict] = {}

    def add(kind, url, mime=""):
        if not isinstance(url, str) or not url.startswith("http") or url in found:
            return
        found[url] = {"type": kind, "url": url, **({"mime": mime} if mime else {})}

    for j in jsons:
        for node in _walk(j or {}):
            for k, v in node.items():
                if not isinstance(v, str) or not v.startswith("http"):
                    continue
                mime = (node.get("mimetype") or node.get("mime") or "").lower() if k == "url" else ""
                kl = k.lower()
                if kl in ("video", "video_stream") or mime.startswith("video/") or VIDEO.search(v) or v.endswith(".m3u8"):
                    add("video", v, mime)
                elif kl in ("audio", "audio_stream") or mime.startswith("audio/") or AUDIO.search(v):
                    add("audio", v, mime)
                elif kl in ("caption", "captions", "transcript_vtt") or mime in ("text/vtt", "application/x-subrip") or CAPTION.search(v):
                    add("caption", v, mime)
                elif kl in ("image", "image_url", "thumb", "thumbnail") or mime.startswith("image/") or "/iiif/" in v or IMAGE.search(v):
                    if not re.search(r"\.(jp2|tiff?)(\?|$)", v, re.I) or "/iiif/" in v:
                        add("image", v, mime)
                elif kl == "pdf" or mime == "application/pdf" or v.lower().endswith(".pdf"):
                    add("pdf", v, mime)
    order = {"video": 0, "audio": 1, "caption": 2, "image": 3, "pdf": 4}
    items = sorted(found.values(), key=lambda m: order[m["type"]])
    out, per = [], {}
    for m in items:                                  # keep the list short: a few of each kind
        cap = {"image": 6, "video": 3, "audio": 3, "caption": 2, "pdf": 1}[m["type"]]
        if per.get(m["type"], 0) < cap:
            per[m["type"]] = per.get(m["type"], 0) + 1
            out.append(m)
    return out[:MAX_MEDIA]


def captions_to_text(raw: bytes) -> str:
    """WebVTT / SRT -> plain transcript text (cue order, timings and numbers removed, repeats collapsed)."""
    t = raw.decode("utf-8", errors="replace").replace("\r", "")
    lines, last = [], ""
    for line in t.split("\n"):
        s = line.strip()
        if not s or s == "WEBVTT" or s.isdigit() or "-->" in s or s.startswith(("NOTE", "STYLE", "Kind:", "Language:")):
            continue
        s = re.sub(r"<[^>]+>", "", s)
        if s != last:
            lines.append(s)
            last = s
    text = " ".join(lines)
    return re.sub(r"\s+", " ", text).strip()


def loc_format(rec: dict, ij: dict | None) -> str:
    fmts = " ".join(L.as_text(x) for x in (rec.get("original_format"), rec.get("online_format"),
                                           (ij or {}).get("item", {}).get("format") if ij else None)).lower()
    for key, name in (("film", "video"), ("video", "video"), ("motion picture", "video"), ("sound", "audio"), ("audio", "audio"),
                      ("map", "map"), ("photo", "image"), ("print", "image"), ("image", "image"), ("manuscript", "manuscript"),
                      ("newspaper", "newspaper"), ("book", "book"), ("periodical", "book")):
        if key in fmts:
            return name
    return "text"


def catalogue_text(*parts) -> str:
    return "\n\n".join(p for p in (L.as_text(x).strip() for x in parts) if p)


# ------------------------------------------------------------------ adapters
class LOC:
    name = "loc.gov"

    def __init__(self, fetcher, per_page=25):
        self.f, self.pp = fetcher, per_page

    def start_url(self, src: str) -> str:
        _, body, fmt = split_src(src)
        if not body.startswith("q:"):
            return L.start_url(body, self.pp)
        q = quote_plus(body[2:])
        if fmt == "books":
            return f"{L.BASE}/search/?q={q}&fa=original-format:book&fo=json&c={self.pp}&sp=1"
        if fmt in LOC_FORMATS:
            return f"{L.BASE}/{fmt}/?q={q}&fo=json&c={self.pp}&sp=1"
        return f"{L.BASE}/search/?q={q}&fo=json&c={self.pp}&sp=1"

    def page(self, url):
        data = self.f.get_json(url)
        if not isinstance(data, dict):
            return None, None
        recs = [r for r in (data.get("results") or []) if isinstance(r, dict)]
        return recs, (data.get("pagination") or {}).get("next")

    def item(self, rec: dict) -> dict | None:
        item_id = L.as_text(rec.get("id") or rec.get("url"))
        if not item_id:
            return None
        api = L.item_api_url(item_id)
        ij = self.f.get_json(api) if api else None
        ij = ij if isinstance(ij, dict) else None
        it = (ij or {}).get("item") or {}
        return {"id": item_id, "title": L.as_text(rec.get("title"))[:300], "date": L.as_text(rec.get("date") or rec.get("dates"))[:40],
                "url": L.as_text(rec.get("url") or item_id), "json": ij, "format": loc_format(rec, ij),
                "thumb": (rec.get("image_url") or [None])[0] if isinstance(rec.get("image_url"), list) else rec.get("image_url"),
                "media": collect_media(rec.get("resources"), (ij or {}).get("resources")),
                "catalogue": catalogue_text(rec.get("title"), rec.get("date"), it.get("summary") or rec.get("description"),
                                            it.get("notes"), rec.get("contributor"), rec.get("subject")),
                "rights": " ".join(L.as_text(it.get(k)) for k in ("rights_advisory", "rights", "rights_information"))}

    def text(self, item: dict) -> str:
        found = L.find_text_url(item["json"]) if item.get("json") else None
        if found:
            kind, turl = found
            raw = self.f.get_bytes(turl)
            if isinstance(raw, (bytes, bytearray)):
                return L.to_text(kind, turl, raw)
        return ""


class IA:
    name = "Internet Archive"
    BASE = "https://archive.org"
    ROWS = 25

    def __init__(self, fetcher, per_page=25):
        self.f = fetcher

    def start_url(self, src: str) -> str:
        _, q, fmt = split_src(src)
        query = f"({q})" + (f" AND mediatype:({fmt})" if fmt in IA_FORMATS else " AND mediatype:(movies OR audio OR texts OR image)")
        fields = "".join(f"&fl[]={x}" for x in ("identifier", "title", "date", "year", "mediatype", "licenseurl"))
        return f"{self.BASE}/advancedsearch.php?q={quote(query)}{fields}&rows={self.ROWS}&page=1&output=json"

    def page(self, url):
        data = self.f.get_json(url)
        if not isinstance(data, dict):
            return None, None
        resp = data.get("response") or {}
        docs = [d for d in resp.get("docs") or [] if isinstance(d, dict)]
        n = int(re.search(r"[?&]page=(\d+)", url).group(1))
        nxt = re.sub(r"([?&]page=)\d+", lambda m: m.group(1) + str(n + 1), url) if n * self.ROWS < int(resp.get("numFound") or 0) else None
        return docs, nxt

    def item(self, rec: dict) -> dict | None:
        ident = rec.get("identifier")
        if not ident:
            return None
        md = self.f.get_json(f"{self.BASE}/metadata/{quote(ident)}")
        md = md if isinstance(md, dict) else {}
        meta = md.get("metadata") or {}
        files = md.get("files") or []
        dl = f"{self.BASE}/download/{quote(ident)}/"
        media, fmts = [], {"movies": "video", "audio": "audio", "texts": "book", "image": "image"}
        for f in files:
            name, fmt = f.get("name", ""), (f.get("format") or "").lower()
            url = dl + quote(name)
            if ("h.264" in fmt or "mpeg4" in fmt or name.lower().endswith(".mp4")) and f.get("source") != "metadata":
                media.append({"type": "video", "url": url, "mime": "video/mp4"})
            elif "mp3" in fmt:
                media.append({"type": "audio", "url": url, "mime": "audio/mpeg"})
            elif CAPTION.search(name):
                media.append({"type": "caption", "url": url})
            elif fmt in ("jpeg", "png") and "thumb" not in name.lower():
                media.append({"type": "image", "url": url})
        caps = {"video": 3, "audio": 3, "caption": 2, "image": 6}
        out, per = [], {}
        for m in media:
            if per.get(m["type"], 0) < caps[m["type"]]:
                per[m["type"]] = per.get(m["type"], 0) + 1
                out.append(m)
        txt = next((dl + quote(f["name"]) for f in files if f.get("name", "").endswith("_djvu.txt")), None)
        year = L.as_text(meta.get("year") or rec.get("year") or meta.get("date") or rec.get("date"))[:40]
        return {"id": f"https://archive.org/details/{ident}", "title": L.as_text(meta.get("title") or rec.get("title"))[:300],
                "date": year, "url": f"https://archive.org/details/{ident}", "json": md,
                "format": fmts.get(meta.get("mediatype") or rec.get("mediatype"), "text"),
                "thumb": f"{self.BASE}/services/img/{quote(ident)}", "media": out[:MAX_MEDIA], "fulltext": txt,
                "catalogue": catalogue_text(meta.get("title"), meta.get("date"), re.sub(r"<[^>]+>", " ", L.as_text(meta.get("description"))),
                                            meta.get("creator"), meta.get("subject")),
                "rights": L.as_text(meta.get("licenseurl") or rec.get("licenseurl")) + " " + L.as_text(meta.get("rights"))}

    def text(self, item: dict) -> str:
        if item.get("fulltext"):
            raw = self.f.get_bytes(item["fulltext"])
            if isinstance(raw, (bytes, bytearray)):
                return raw.decode("utf-8", errors="replace")
        return ""


def adapter_for(src: str, fetcher, per_page=25):
    return IA(fetcher, per_page) if src.startswith("ia:") else LOC(fetcher, per_page)
