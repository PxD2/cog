#!/usr/bin/env python3
"""Hall of Presidents — publish every president and every inaugural address into the COG library on GitHub.

    roster   sections/presidents/roster.json   (number, name, years, party, state, a one-line note for young readers)
    speeches section "presidents": each inaugural address as COG addresses (word for word, public domain),
             with its date, occasion, word count and the address of its best-known line.

Speech text comes from the C-SPAN inaugural address corpus (NLTK corpora, inaugural.zip, 1789–2025).
More speeches (Gettysburg, fireside chats, recordings) come in through the COG Absorber into the same section.

    python publish_presidents.py --corpus path/to/inaugural            # push to PxD2/cog
    python publish_presidents.py --corpus path/to/inaugural --local ../cog
"""
from __future__ import annotations

import argparse, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cog_absorber as A        # noqa: E402
from cog import segments        # noqa: E402

SECTION, TITLE = "presidents", "Hall of Presidents"
ROSTER_PATH = "sections/presidents/roster.json"

# number, name, short, took office, left office (None = serving), party, home state, note for young readers
ROSTER = [
    (1, "George Washington", "Washington", 1789, 1797, "None", "Virginia", "Led the Continental Army, then became the first president and set the two-term tradition."),
    (2, "John Adams", "Adams", 1797, 1801, "Federalist", "Massachusetts", "Helped write the case for independence and was the first president to live in the White House."),
    (3, "Thomas Jefferson", "Jefferson", 1801, 1809, "Democratic-Republican", "Virginia", "Wrote the Declaration of Independence and bought the Louisiana Territory."),
    (4, "James Madison", "Madison", 1809, 1817, "Democratic-Republican", "Virginia", "Called the Father of the Constitution; led the country in the War of 1812."),
    (5, "James Monroe", "Monroe", 1817, 1825, "Democratic-Republican", "Virginia", "Warned Europe to stay out of the Americas in the Monroe Doctrine."),
    (6, "John Quincy Adams", "J. Q. Adams", 1825, 1829, "Democratic-Republican", "Massachusetts", "Son of John Adams; later fought slavery in Congress."),
    (7, "Andrew Jackson", "Jackson", 1829, 1837, "Democratic", "Tennessee", "War of 1812 general who called himself the people's president."),
    (8, "Martin Van Buren", "Van Buren", 1837, 1841, "Democratic", "New York", "The first president born a citizen of the United States."),
    (9, "William Henry Harrison", "W. H. Harrison", 1841, 1841, "Whig", "Ohio", "Gave the longest inaugural address and served only 31 days."),
    (10, "John Tyler", "Tyler", 1841, 1845, "Whig", "Virginia", "The first vice president to become president when a president died."),
    (11, "James K. Polk", "Polk", 1845, 1849, "Democratic", "Tennessee", "The country grew west to the Pacific while he was president."),
    (12, "Zachary Taylor", "Taylor", 1849, 1850, "Whig", "Louisiana", "A general in the Mexican–American War who died in office."),
    (13, "Millard Fillmore", "Fillmore", 1850, 1853, "Whig", "New York", "Became president when Taylor died; signed the Compromise of 1850."),
    (14, "Franklin Pierce", "Pierce", 1853, 1857, "Democratic", "New Hampshire", "Signed the Kansas–Nebraska Act, which deepened the split over slavery."),
    (15, "James Buchanan", "Buchanan", 1857, 1861, "Democratic", "Pennsylvania", "President as Southern states began to leave the Union."),
    (16, "Abraham Lincoln", "Lincoln", 1861, 1865, "Republican", "Illinois", "Led the Union through the Civil War and worked to end slavery."),
    (17, "Andrew Johnson", "A. Johnson", 1865, 1869, "National Union", "Tennessee", "Became president after Lincoln was killed; the first president impeached."),
    (18, "Ulysses S. Grant", "Grant", 1869, 1877, "Republican", "Illinois", "The Union's top general in the Civil War."),
    (19, "Rutherford B. Hayes", "Hayes", 1877, 1881, "Republican", "Ohio", "His presidency ended Reconstruction in the South."),
    (20, "James A. Garfield", "Garfield", 1881, 1881, "Republican", "Ohio", "Shot a few months into his term; died that September."),
    (21, "Chester A. Arthur", "Arthur", 1881, 1885, "Republican", "New York", "Signed a law so many government jobs went to people who passed tests."),
    (22, "Grover Cleveland", "Cleveland", 1885, 1889, "Democratic", "New York", "The only president to serve two terms that were not back to back (22nd and 24th)."),
    (23, "Benjamin Harrison", "B. Harrison", 1889, 1893, "Republican", "Indiana", "Grandson of William Henry Harrison; six states joined while he was president."),
    (24, "Grover Cleveland", "Cleveland", 1893, 1897, "Democratic", "New York", "Back for a second, separate term — counted twice."),
    (25, "William McKinley", "McKinley", 1897, 1901, "Republican", "Ohio", "President during the Spanish–American War; shot in 1901."),
    (26, "Theodore Roosevelt", "T. Roosevelt", 1901, 1909, "Republican", "New York", "Protected millions of acres of forests and parks; started the Panama Canal."),
    (27, "William Howard Taft", "Taft", 1909, 1913, "Republican", "Ohio", "Later became Chief Justice of the Supreme Court."),
    (28, "Woodrow Wilson", "Wilson", 1913, 1921, "Democratic", "New Jersey", "Led the country in World War I."),
    (29, "Warren G. Harding", "Harding", 1921, 1923, "Republican", "Ohio", "Promised a return to normal life after the war; died in office."),
    (30, "Calvin Coolidge", "Coolidge", 1923, 1929, "Republican", "Massachusetts", "Known as Silent Cal for saying few words."),
    (31, "Herbert Hoover", "Hoover", 1929, 1933, "Republican", "California", "President when the Great Depression began."),
    (32, "Franklin D. Roosevelt", "F. D. Roosevelt", 1933, 1945, "Democratic", "New York", "Elected four times; led through the Great Depression and World War II."),
    (33, "Harry S. Truman", "Truman", 1945, 1953, "Democratic", "Missouri", "Ended World War II and helped rebuild Europe."),
    (34, "Dwight D. Eisenhower", "Eisenhower", 1953, 1961, "Republican", "Kansas", "Commanded the D-Day invasion; built the interstate highways."),
    (35, "John F. Kennedy", "Kennedy", 1961, 1963, "Democratic", "Massachusetts", "Set the goal of landing a person on the Moon."),
    (36, "Lyndon B. Johnson", "L. B. Johnson", 1963, 1969, "Democratic", "Texas", "Signed the Civil Rights Act of 1964 and the Voting Rights Act of 1965."),
    (37, "Richard Nixon", "Nixon", 1969, 1974, "Republican", "California", "Opened ties with China; the only president to resign."),
    (38, "Gerald Ford", "Ford", 1974, 1977, "Republican", "Michigan", "The only president never elected president or vice president."),
    (39, "Jimmy Carter", "Carter", 1977, 1981, "Democratic", "Georgia", "Helped make peace between Egypt and Israel at Camp David."),
    (40, "Ronald Reagan", "Reagan", 1981, 1989, "Republican", "California", "Former actor and governor; president as the Cold War neared its end."),
    (41, "George H. W. Bush", "G. H. W. Bush", 1989, 1993, "Republican", "Texas", "President when the Berlin Wall fell and during the Gulf War."),
    (42, "Bill Clinton", "Clinton", 1993, 2001, "Democratic", "Arkansas", "President during a long run of economic growth in the 1990s."),
    (43, "George W. Bush", "G. W. Bush", 2001, 2009, "Republican", "Texas", "Son of George H. W. Bush; president on September 11, 2001."),
    (44, "Barack Obama", "Obama", 2009, 2017, "Democratic", "Illinois", "The first African American president."),
    (45, "Donald Trump", "Trump", 2017, 2021, "Republican", "New York", "Businessman who became president without holding office before."),
    (46, "Joe Biden", "Biden", 2021, 2025, "Democratic", "Delaware", "Served 36 years in the Senate and was vice president before."),
    (47, "Donald Trump", "Trump", 2025, None, "Republican", "Florida", "Returned for a second, separate term — counted twice, like Cleveland."),
]

# inaugural year -> presidency number
YEAR_TO_N = {1789: 1, 1793: 1, 1797: 2, 1801: 3, 1805: 3, 1809: 4, 1813: 4, 1817: 5, 1821: 5, 1825: 6, 1829: 7, 1833: 7, 1837: 8,
             1841: 9, 1845: 11, 1849: 12, 1853: 14, 1857: 15, 1861: 16, 1865: 16, 1869: 18, 1873: 18, 1877: 19, 1881: 20,
             1885: 22, 1889: 23, 1893: 24, 1897: 25, 1901: 25, 1905: 26, 1909: 27, 1913: 28, 1917: 28, 1921: 29, 1925: 30,
             1929: 31, 1933: 32, 1937: 32, 1941: 32, 1945: 32, 1949: 33, 1953: 34, 1957: 34, 1961: 35, 1965: 36, 1969: 37,
             1973: 37, 1977: 39, 1981: 40, 1985: 40, 1989: 41, 1993: 42, 1997: 42, 2001: 43, 2005: 43, 2009: 44, 2013: 44,
             2017: 45, 2021: 46, 2025: 47}

# best-known lines: matched against the real text; a line is only used if it is found word for word
KEY_LINES = {
    1801: "We are all Republicans, we are all Federalists",
    1861: "We are not enemies, but friends",
    1865: "With malice toward none",
    1933: "the only thing we have to fear is fear itself",
    1961: "ask not what your country can do for you",
    1981: "government is not the solution to our problem",
    1993: "There is nothing wrong with America that cannot be cured by what is right with America",
    1969: "The greatest honor history can bestow is the title of peacemaker",
    2009: "we have chosen hope over fear",
    1797: "Without virtue, no republic",
    1829: "the will of the people",
    1905: "We have become a great nation",
    1913: "This is not a day of triumph; it is a day of dedication",
    1949: "the peoples of the earth face the future with grave uncertainty",
}
NO_INAUGURAL = {10: "Became president when William Henry Harrison died, so he gave no inaugural address.",
                13: "Became president when Zachary Taylor died, so he gave no inaugural address.",
                17: "Became president when Lincoln was killed, so he gave no inaugural address.",
                21: "Became president when Garfield died, so he gave no inaugural address.",
                38: "Became president when Nixon resigned; he spoke to the nation but gave no inaugural address."}


def roster_json() -> dict:
    out = []
    for n, name, short, a, b, party, state, note in ROSTER:
        out.append({"n": n, "name": name, "short": short, "from": a, "to": b, "party": party, "state": state, "note": note,
                    **({"no_inaugural": NO_INAUGURAL[n]} if n in NO_INAUGURAL else {})})
    return {"name": "presidents/roster", "ver": 1, "section": SECTION, "as_of": "2026",
            "note": "One entry per presidency (Cleveland and Trump each appear twice, as the official numbering counts them).",
            "presidents": out}


def publish(store, corpus: Path, log=print) -> dict:
    lib = A.Library(store, log)
    lib.section(SECTION, TITLE, "core")
    names = {n: name for n, name, *_ in ROSTER}
    done = skipped = 0
    keys_found = []
    for p in sorted(corpus.glob("*.txt")):
        m = re.match(r"(\d{4})-", p.name)
        if not m:
            continue
        year = int(m.group(1))
        n = YEAR_TO_N.get(year)
        if not n:
            log(f"  skipped {p.name}: no presidency for {year}")
            continue
        raw = p.read_bytes()
        text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").strip()
        text = re.sub(r"\n(?!\n)", "\n\n", text)                 # one paragraph per line in the corpus
        key = f"speech:inaugural:{year}@{hashlib.sha1(raw).hexdigest()[:10]}"
        if lib.seen(key):
            skipped += 1
            continue
        nth = sum(1 for y, k in YEAR_TO_N.items() if k == n and y <= year)
        title = f"{'Second ' if nth == 2 else 'Third ' if nth == 3 else 'Fourth ' if nth == 4 else 'First ' if any(k == n and y != year for y, k in YEAR_TO_N.items()) else ''}Inaugural Address"
        meta = {"title": f"{names[n]} — {title}", "date": str(year), "kind": "speech", "pres": n, "occasion": title,
                "words": len(re.findall(r"[A-Za-z']+", text)), "source": "C-SPAN inaugural address corpus (NLTK)",
                "url": "https://www.nltk.org/nltk_data/", "format": "text", "archive": "C-SPAN corpus"}
        seq, _ = lib.encode(text)          # numbers first so the key line's address is known
        addrs = [t for t in seq if t != "|"]
        sents = [A.norm_sentence(s) for s in segments(text) if A.norm_sentence(s)]
        phrase = KEY_LINES.get(year)
        if phrase:
            hit = next((i for i, s in enumerate(sents) if phrase.lower() in s.lower()), None)
            if hit is not None and hit < len(addrs):
                meta["key"] = addrs[hit]
                meta["key_text"] = sents[hit]
                keys_found.append(year)
            else:
                log(f"  key line not found word for word in {year}; left out")
        lib.add_doc(key, meta, text, SECTION)
        done += 1
    roster = json.dumps(roster_json(), ensure_ascii=False, indent=1).encode()
    if not done and store.get(ROSTER_PATH) == roster:
        log(f"Nothing new: {skipped} speeches unchanged, roster unchanged")
        return {"published": 0, "unchanged": skipped, "keys": [], "commit": None}
    files_extra = {ROSTER_PATH: roster}
    lib.dirty.add("r")
    core, ext = lib._files_for(lib.dirty)
    core.update(files_extra)
    sha = lib._commit(core, ext, f"Hall of Presidents: roster + {done} inaugural address(es) as COG")
    lib.dirty.clear()
    log(f"Published {done} speeches ({skipped} unchanged), {len(keys_found)} best-known lines found, roster of {len(ROSTER)} presidencies"
        f" · next free meaning-id {lib.state['next_meaning']}")
    return {"published": done, "unchanged": skipped, "keys": keys_found, "commit": sha}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, help="folder with 1789-Washington.txt … (NLTK inaugural corpus)")
    ap.add_argument("--local", help="write into a local clone of PxD2/cog instead of pushing")
    a = ap.parse_args(argv)
    store = A.LocalStore(a.local) if a.local else A.GitHubStore()
    if not a.local and not store.token:
        print("No GitHub sign-in found.")
        return 2
    publish(store, Path(a.corpus))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
