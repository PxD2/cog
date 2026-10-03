# COG

**PXD2 Digital Library** — dual-number sequential sentence packs

Live site (after GitHub Pages is enabled on `main` / root):
https://pxd2.github.io/cog/

## What it is
A walkable digital library (modern Encarta-style) built on the smallest practical packs:

- **meaning-id** = one number for the shared meaning
- **variant-index** = second number for the exact surface sentence

Wire form is only the pair `(meaning-id, variant-index)`.  
Full text is recovered only after the shared kind-3 book is already mounted.

## Rooms
| Room | Book | IDs |
|------|------|-----|
| English Hall | `books/cog-english-v0.json` | 1 |
| Physics Wing | `books/cog-physics-v0.json` | 100–104 |
| Philosophy Wing | `books/cog-philosophy-v0.json` | 200–204 |

## Site features
- Walk-through rooms via sidebar or top nav
- Fast Transport jumps straight to any meaning-id
- Click any card → expands exact variants with dual-number address
- Single ~8 KB HTML + tiny JSON packs (no framework, no bloat)

## Enable the site
1. Repo → Settings → Pages
2. Source: Deploy from a branch
3. Branch: `main` / root
4. Save → site appears at https://pxd2.github.io/cog/

## Rules
- Public demo seeds only
- No production lexicon
- No invented ids beyond these finite packs
- Public contract remains `PxD2/lex`
- Receipt only until Dialect-1 Accept
