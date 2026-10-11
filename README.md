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

## Alexandria — the reader (PC + VR)

https://pxd2.github.io/cog/alexandria/

A modern encyclopedia built only from these packs: articles at two reading levels (K–5 / 6–12), read-aloud, quizzes,
timeline, atlas, primary sources, media (films, recordings, photos, maps streamed from the archive), instant search over every sentence, and a tutor that answers only from the library
(each quote shows its address). "Enter the Hall" opens a 3D Great Hall; in a VR headset browser it becomes WebXR.
COG numbers stay hidden until you press `#`. Articles: `sections/encyclopedia/` (published by `tools/publish_articles.py`).
Optional: the tutor can use base1's Ollama (start it with `OLLAMA_ORIGINS=https://pxd2.github.io`).

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
  core-m-NNNN.json  shared meaning packs (absorbed texts + articles)  [meaning-id, keys, [first-variant], [variants]]
  catalog.json      every book + meaning-id ranges (the site reads this)
sections/<name>/    library sections: docs-NNNN.json = documents as address lines "1000.0 1007.2 | 1012.0" (| = paragraph)
loc/state.json      next free meaning-id, open files, sections (title + where stored), where each source left off
loc/registry/       lookup segments: meaning hash -> id, sentence hash -> address, item -> doc pack
plates/             PMOC-ready inspectable twins
tools/              cog_absorber.py (engine) + cog_absorber_gui.py (window) + library_desk.py (agent desk) + publish_articles.py + cog_vault_sync.py (Obsidian mirror)
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
Sources: the Library of Congress (any format: books, film-and-videos, audio, photos, maps, manuscripts, newspapers) and the
Internet Archive (movies, audio, texts, image). Films, recordings and pictures are never copied here — GitHub rejects files
over 100 MB and the library stays small — so each keeps its catalogue text and captions/transcript as COG plus stream links.
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
