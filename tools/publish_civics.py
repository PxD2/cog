#!/usr/bin/env python3
"""Publish Alexandria's civics layer to the COG library on GitHub (PxD2/cog), section "civics":

    sections/civics/congresses.json     every Congress (1st 1789 … 119th 2025) with the presidencies it served with
    landmark documents                  laws, amendments, Supreme Court cases, founding acts — each line stored as COG,
                                        tagged with its date, Congress number and president
    sections/civics/threads/*.json      guided threads (the first: The Covenant Republic), every station's text as COG

    python publish_civics.py            # push
    python publish_civics.py --local ../cog
"""
from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path
from urllib.parse import quote_plus

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cog_absorber as A            # noqa: E402
import civics_data as D             # noqa: E402
from publish_presidents import ROSTER   # noqa: E402

SECTION, TITLE = "civics", "Laws, Amendments & the Court"
STARTS = ["1789-04-30", "1797-03-04", "1801-03-04", "1809-03-04", "1817-03-04", "1825-03-04", "1829-03-04", "1837-03-04", "1841-03-04",
          "1841-04-04", "1845-03-04", "1849-03-04", "1850-07-09", "1853-03-04", "1857-03-04", "1861-03-04", "1865-04-15", "1869-03-04",
          "1877-03-04", "1881-03-04", "1881-09-19", "1885-03-04", "1889-03-04", "1893-03-04", "1897-03-04", "1901-09-14", "1909-03-04",
          "1913-03-04", "1921-03-04", "1923-08-02", "1929-03-04", "1933-03-04", "1945-04-12", "1953-01-20", "1961-01-20", "1963-11-22",
          "1969-01-20", "1974-08-09", "1977-01-20", "1981-01-20", "1989-01-20", "1993-01-20", "2001-01-20", "2009-01-20", "2017-01-20",
          "2021-01-20", "2025-01-20"]
assert len(STARTS) == len(ROSTER) == 47


def norm(d: str) -> str:
    parts = (d.split("-") + ["01", "01"])[:3]
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def president_for(date: str) -> int | None:
    d = norm(date)
    if d < STARTS[0]:
        return None
    n = None
    for i, s in enumerate(STARTS):
        if s <= d:
            n = i + 1
    return n


def congresses() -> list[dict]:
    out = []
    for n in range(1, 120):
        a, b = D.congress_years(n)
        start = f"{a}-03-04" if a < 1935 else f"{a}-01-03"
        end = f"{b}-03-04" if b < 1935 else f"{b}-01-03"
        pres = sorted({president_for(start) or 1} | {i + 1 for i, s in enumerate(STARTS) if start <= s < end})
        out.append({"n": n, "from": a, "to": b, "presidents": pres})
    return out


def loc_link(kind: str, title: str) -> str:
    if kind == "case":
        return f"https://www.loc.gov/collections/united-states-reports/?q={quote_plus(title.split(' (')[0])}"
    if kind in ("law", "amendment"):
        return f"https://www.loc.gov/search/?q={quote_plus(title)}&fa=partof:a+century+of+lawmaking+for+a+new+nation"
    return f"https://www.loc.gov/search/?q={quote_plus(title)}"


def publish(store, log=print) -> dict:
    lib = A.Library(store, log)
    lib.section(SECTION, TITLE, "core")
    done = 0
    for date, kind, title, line in D.LANDMARKS:
        key = f"civics:{title}@{hashlib.sha1((date + kind + title + line).encode()).hexdigest()[:10]}"
        if lib.seen(key):
            continue
        meta = {"title": title, "date": date, "kind": "landmark", "lk": kind, "pres": president_for(date),
                "congress": D.congress_for(date), "url": loc_link(kind, title), "source": "Alexandria civics", "format": "text"}
        lib.add_doc(key, meta, line, SECTION)
        # the finder index carries kind + congress too
        lib._ipack(SECTION)["e"][-1].update({"lk": kind, "cg": meta["congress"]} if meta["congress"] else {"lk": kind})
        done += 1
    # the thread: stations in date order, each station's text as COG addresses
    th = dict(D.THREAD)
    stations = []
    for date, title, text, links in sorted(D.THREAD["stations"], key=lambda s: norm(s[0])):
        seq, _ = lib.encode(text)
        stations.append({"date": date, "title": title, "seq": " ".join(seq), "links": links, "pres": president_for(date)})
    th["stations"] = stations
    th.pop("about", None)
    about_seq, _ = lib.encode(D.THREAD["about"])
    th["about_seq"] = " ".join(about_seq)
    extra = {f"sections/{SECTION}/congresses.json": json.dumps({"name": "congresses", "congresses": congresses()}, indent=0).encode(),
             f"sections/{SECTION}/threads/{th['id']}.json": json.dumps(th, ensure_ascii=False, indent=1).encode(),
             f"sections/{SECTION}/threads/index.json": json.dumps({"threads": [{"id": th["id"], "title": th["title"], "subtitle": th["subtitle"],
                                                                                "scribes": th["scribes"], "stations": len(stations)}]}, ensure_ascii=False).encode()}
    lib.dirty.add("r")
    lib.dirty.add("i:" + SECTION)
    core, ext = lib._files_for(lib.dirty)
    core.update(extra)
    sha = lib._commit(core, ext, f"Alexandria civics: {done} landmarks, 119 Congresses, thread '{th['title']}'")
    log(f"Published {done} landmarks, 119 Congresses, {len(stations)} thread stations · next free meaning-id {lib.state['next_meaning']}")
    return {"published": done, "commit": sha}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local")
    a = ap.parse_args(argv)
    store = A.LocalStore(a.local) if a.local else A.GitHubStore()
    if not a.local and not store.token:
        print("No GitHub sign-in found.")
        return 2
    publish(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
