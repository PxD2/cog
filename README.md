# COG

**Permanent library of human meanings.**

Every distinct meaning receives one permanent number.  
Every exact surface sentence under that meaning receives a second number.

The pair `(meaning-id, variant-index)` is the complete address.  
Nothing else travels. The full sentence is recovered only after the shared book is mounted.

---

## Why this exists

- Addresses never break.
- One shared book of meanings replaces endless duplicated text.
- Everything lives on GitHub. Nothing stays on your machine.
- Growth is pure append: next free meaning-id or next variant-index.
- The same packs power a walkable digital library and future VR rooms.

## Live library

https://pxd2.github.io/cog/

(Enable GitHub Pages on `main` / root if not already live.)

## Numerical sequence

| Range | Domain |
|-------|--------|
| 1 | English inquiry |
| 100–104 | Physics core |
| 200–204 | Philosophy core |
| 300+ | Open |
| 1000+ | Absorbed from the Library of Congress (assigned by the absorber, in order) |

## Structure

```
books/              dual-number packs (JSON)
  loc-m-NNNN.json   absorbed meaning packs  [meaning-id, keys, [first-variant], [variants]]
  catalog.json      every book + meaning-id ranges (the site reads this)
sections/<name>/    library sections: docs-NNNN.json = documents as address lines "1000.0 1007.2 | 1012.0" (| = paragraph)
loc/state.json      next free meaning-id, open files, sections (title + where stored), where each source left off
loc/registry/       lookup segments: meaning hash -> id, sentence hash -> address, item -> doc pack
plates/             PMOC-ready inspectable twins
tools/              cog_absorber.py (engine) + cog_absorber_gui.py (window) + library_desk.py (agent desk, local Ollama)
index.html          walkable digital library (Library of Congress room reads the absorbed packs)
```

## Absorber (Library of Congress -> COG, on request only)

The Library of Congress is a taxpayer trust: held in trust for the people who paid for it, not a government organization or entity.

`tools/cog_absorber.py` pulls loc.gov items into memory, splits them into sentences, gives each new meaning the next free
number (from 1000) and each new exact wording the next variant index, and pushes only the delta here with the Git Data API.
No clone and no local library. Files are rewritten only while they are the open one (< 1 MB); closed files never change.
Documents are held in **library sections** (Law, The Reformers, ...). Each section has its own storage spot: a folder
here (`sections/<name>/`) or its own repository (`owner/repo`). Meaning-ids stay global: one registry in core, so the
same sentence has the same address in every section. Section repos are written first, core second, so core never
points at a document that is not there. The site reads core sections directly and public section repos via raw GitHub.
A rights gate holds back anything after 1930 without an open-rights statement, because this repo is public.

```
python tools/cog_absorber.py --query "Samuel Rutherford" --books --items 10
python tools/cog_absorber.py --collection century-of-lawmaking --items 25
python tools/cog_absorber.py --status
```

## Rules

- Never rewrite an existing meaning-id.
- Keep every pack under 1 MB.
- Push only the delta.
- No production lexicon invented here.
- Public contract remains `PxD2/lex`.

## One sentence

A permanent, append-only library of meanings, addressed by two numbers, stored only on GitHub, grown one exact sentence at a time.
