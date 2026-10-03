# COG

**PXD2 Closed English Meaning-Variant Lexicon**

Dual-number sequential sentence system:

- **meaning-id** = sole number for the shared meaning
- **variant-index** = which exact surface phrase of that meaning

Wire form is only the pair `(meaning-id, variant-index)`.  
Full phrase is recovered only after the shared kind-3 book is mounted.

## Books (finite public demo seeds)

| Book | Path | Meaning-id range |
|------|------|------------------|
| English inquiry | `books/cog-english-v0.json` | 1 |
| Physics core | `books/cog-physics-v0.json` | 100–104 |
| Philosophy core | `books/cog-philosophy-v0.json` | 200–204 |

Matching inspectable plates live under `plates/`.

## Chapter 1 — English (meaning-id 1)
Inquiry into current situation / status / activity (30 variants).  
Example: `(1, 5)` → sitrep

## Chapter 2 — Physics (meaning-ids 100–104)

| id | keys | sample exact phrases |
|----|------|----------------------|
| 100 | force, newton | F = ma · Newton's second law |
| 101 | energy, conservation | energy cannot be created or destroyed |
| 102 | gravity, newtonian | Newton's law of universal gravitation |
| 103 | relativity, einstein | E = mc² · space and time are relative |
| 104 | quantum, uncertainty | Heisenberg uncertainty principle |

## Chapter 3 — Philosophy (meaning-ids 200–204)

| id | keys | sample exact phrases |
|----|------|----------------------|
| 200 | existence, ontology | I think therefore I am · cogito ergo sum |
| 201 | knowledge, epistemology | knowledge is justified true belief |
| 202 | ethics, morality | the greatest good for the greatest number |
| 203 | free_will, determinism | do we have free will · compatibilism |
| 204 | truth, correspondence | truth is correspondence with reality |

## Rules
- No production lexicon.
- No invented ids beyond these finite public seeds.
- Public contract remains `PxD2/lex`.
- Receipt only until Dialect-1 Accept.
