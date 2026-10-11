#!/usr/bin/env python3
"""Publish Alexandria's encyclopedia articles (content/articles/*.md) into the COG library on GitHub.

Each article goes into the "encyclopedia" section: both reading levels as address lines (global meaning-ids, shared
with everything else in the library), plus its quiz, year, place, related articles and summary. An edited article is
published again as a new entry (append-only); the reader shows the newest one. Unchanged articles are skipped.

    python publish_articles.py                       # push to PxD2/cog (GitHub sign-in as for the absorber)
    python publish_articles.py --dry-run             # show what would be published
    python publish_articles.py --local ../cog        # write into a local clone instead (then git push yourself)
"""
from __future__ import annotations

import argparse, hashlib, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cog_absorber as A        # noqa: E402

SECTION, TITLE = "encyclopedia", "Encyclopedia"


def parse(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: missing --- front matter")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    secs = {h.strip().lower(): t.strip() for h, t in re.findall(r"^##\s+(.+?)\s*\n(.*?)(?=^##\s|\Z)", m.group(2), re.S | re.M)}
    place = meta.get("place", "")
    art = {
        "id": "article:" + path.stem,
        "title": meta.get("title") or path.stem.replace("-", " ").title(),
        "subject": meta.get("subject") or "General",
        "year": int(meta["year"]) if re.fullmatch(r"-?\d+", meta.get("year", "") or "") else None,
        "place": [float(x) for x in place.split(",")] if re.fullmatch(r"\s*-?[\d.]+\s*,\s*-?[\d.]+\s*", place) else None,
        "related": [r.strip() for r in (meta.get("related") or "").split(";") if r.strip()],
        "summary": meta.get("summary", ""),
        "texts": {"young": secs.get("young readers", ""), "deeper": secs.get("explore deeper", "")},
        "quiz": [],
    }
    for line in secs.get("quiz", "").splitlines():
        parts = [p.strip() for p in line.lstrip("-* ").split("|")]
        if len(parts) == 4 and parts[0] in ("young", "deeper"):
            choices = [c.strip() for c in parts[2].split(";") if c.strip()]
            try:
                ans = int(parts[3]) - 1
            except ValueError:
                continue
            if 0 <= ans < len(choices):
                art["quiz"].append({"level": parts[0], "q": parts[1], "choices": choices, "answer": ans})
    if not any(art["texts"].values()):
        raise ValueError(f"{path.name}: needs '## Young readers' or '## Explore deeper'")
    return art


def publish(store, folder: Path, log=print) -> dict:
    lib = A.Library(store, log)
    lib.section(SECTION, TITLE, "core")
    done = skipped = 0
    errors = []
    for p in sorted(folder.glob("*.md")):
        key = f"article:{p.stem}@{hashlib.sha1(p.read_bytes()).hexdigest()[:10]}"
        if lib.seen(key):
            skipped += 1
            continue
        try:
            art = parse(p)
        except Exception as e:      # noqa: BLE001
            errors.append(str(e))
            continue
        n = lib.add_article(key, SECTION, art)
        done += 1
        log(f"  {art['title']}: {n} sentences")
    sha = lib.flush(f"Alexandria: publish {done} encyclopedia article(s) as COG addresses") if done else None
    log(f"Published {done}, unchanged {skipped}" + (f", errors: {'; '.join(errors)}" if errors else "")
        + f" · next free meaning-id {lib.state['next_meaning']}")
    return {"published": done, "unchanged": skipped, "errors": errors, "commit": sha}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--articles", default=str(HERE / "content" / "articles"))
    ap.add_argument("--local", help="write into this local clone of PxD2/cog instead of pushing")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repo", default=A.REPO)
    a = ap.parse_args(argv)
    if a.local:
        store = A.LocalStore(a.local)
    elif a.dry_run:
        gh = A.GitHubStore(a.repo)
        gh.refresh()
        store = A.MemStore({p: gh.get(p) for p in gh.tree if p.startswith(("loc/", "books/", "sections/"))})
    else:
        store = A.GitHubStore(a.repo)
        if not store.token:
            print("No GitHub sign-in found (gh auth login, or GITHUB_TOKEN).")
            return 2
    publish(store, Path(a.articles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
