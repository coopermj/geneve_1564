# Edition Consolidation — Design

**Date:** 2026-06-07
**Branch:** `chore/consolidate-editions`
**Status:** Approved design, pending implementation plan

## Goal

Collapse the three diverged edition branches (master/ESV, `feature/net-notes`,
`feature/geneva-annotations`) into a **single branch/directory** where every
edition builds from one place via CLI-selectable targets, sharing code by
definition. This eliminates the recurring cross-branch merge tax and makes a
shared fix apply to all editions instantly.

This is the "option (a)" consolidation. It supersedes the branch-per-edition
model (option b cleanup — already done — kept that model but reduced its pain).

## Scope: editions

**Five compile targets** (CLI-selectable, plus `all`):

| Target | Main doc | Translation | Layout |
|---|---|---|---|
| `esv` | `esv_bible.tex` | ESV | two-column reading, red-letter, verse-number protrusion |
| `net-reading` | `net_reading.tex` | NET | reading edition (renamed from master's `net_bible.tex`) |
| `net-notes` | `net_notes.tex` | NET | single-column, wide right gutter for notes |
| `geneva` | `geneva_bible.tex` | NET | + 15k Geneva 1564 margin annotations (renamed from geneva's `net_bible.tex`) |
| `geneve-1564` | `geneve_1564.tex` | French | legacy original |

**Three generation outputs** (book `.tex`): `esv`, `net` (plain), `geneva`
(annotated). `net-reading` and `net-notes` consume the **same** generated
`net` book files — they differ only in main doc, layout, cover, and index.

## Directory layout

```
# Main documents (repo root) — one per compile target
esv_bible.tex
net_reading.tex          (← master net_bible.tex)
net_notes.tex            (← net-notes)
geneva_bible.tex         (← geneva net_bible.tex)
geneve_1564.tex          (legacy French)

# Tracked, hand-crafted per-edition assets
editions/esv/{cover.tex, color_index.tex}
editions/net_reading/{cover.tex, color_index.tex}
editions/net_notes/{cover.tex, color_index.tex}
editions/geneva/{cover.tex, color_index.tex}

# Generated book files — GITIGNORED, regenerated on build
livres_esv/      ESV book .tex + old_testament.tex + new_testament.tex
livres_net/      NET plain book .tex + includes (shared: net-reading + net-notes)
livres_geneva/   NET annotated book .tex + includes

# Shared (tracked)
scripts/         generate.py + esv_latex_generator.py + latex_generator.py +
                 fetchers + annotation_fetcher.py + overlap_detector.py + bible_config.py
scripture.sty    fonts/    verse_protrusion.tex    reading_plan.tex
data/            esv_cache/, net_bible_cache/ (gitignored); geneva_*.json (force-added)
livres/genese/   legacy French inputs for geneve_1564.tex (untouched)
```

Each main doc `\input`s its own `editions/<name>/cover`,
`editions/<name>/color_index`, and its generated `livres_<gen>/`
(`old_testament`, `new_testament`, book files). `geneve_1564.tex` keeps its
existing `livres/genese/…` inputs.

### Name-collision resolution

`net_bible.tex` exists on multiple branches with different content (master =
NET reading; geneva = annotated). Resolved by renaming to **`net_reading.tex`**
and **`geneva_bible.tex`** respectively.

### Tracked vs generated

- **Tracked:** main docs; `editions/<name>/` covers + color-indexes (hand-crafted
  / hand-tuned, so tracked to avoid regeneration clobbering them); all scripts;
  `scripture.sty`; fonts; `verse_protrusion.tex`; `reading_plan.tex`; annotation
  data JSON.
- **Gitignored / regenerated:** `livres_esv/`, `livres_net/`, `livres_geneva/`
  book files and their `old_testament.tex` / `new_testament.tex` include lists.

## Unified generation script

`scripts/generate.py --edition {esv,net,geneva,all}` replaces the three forked
entry scripts (`generate_esv.py`, `generate_bible.py`, `build_annotated.py`).
Dispatch:

| `--edition` | generator module | fetcher / cache | annotations | output dir |
|---|---|---|---|---|
| `esv` | `esv_latex_generator` | `esv_fetcher` / `data/esv_cache` | — | `livres_esv/` |
| `net` | `latex_generator` | `bible_fetcher` / `data/net_bible_cache` | off | `livres_net/` |
| `geneva` | `latex_generator` | `bible_fetcher` / `data/net_bible_cache` | on | `livres_geneva/` |
| `all` | — | — | — | loop esv, net, geneva |

- Generates book `.tex` + `old_testament.tex` / `new_testament.tex` only. Does
  not touch tracked `editions/<name>/` assets.
- The `(b)` work already made NET-vs-geneva a single optional flag on
  `latex_generator.generate_book_tex`; `--edition geneva` sets it and supplies
  the annotation data + corrections.
- `--edition geneva` **orchestrates the existing annotation pipeline**
  (inject `\gva`/`\marginnote` → compile → PyMuPDF overlap detection →
  correction pass → recompile). It does not rewrite that pipeline.
- A `--no-regen` flag / Make dependency check skips fetching when the output
  dir is already current.
- The old three scripts are removed; their tests are repointed at `generate.py`.

## Data seeding (no re-download)

The consolidated build seeds **entirely from previously-downloaded data —
fully offline, no API re-fetch and no Geneva re-scrape**:

- **Bible text:** `data/esv_cache/` (1189 chapters) and `data/net_bible_cache/`
  (1189 chapters) are already present on the branch (inherited from master) and
  complete. `generate.py` reads chapter JSON from these; it only hits the
  network on a cache miss, which will not occur for a full edition.
- **Geneva annotations:** `data/geneva_annotations.json` (the 15k scraped
  notes), `data/geneva_arguments.json`, and `data/corrections_final.json` are
  copied in from the geneva branch (where they are force-added). The
  `geneva` generation reuses these directly. `note_manifest.json` is a
  build-derived artifact and is regenerated, not seeded.

No step in the migration or build requires re-downloading or re-scraping any
source data.

## Build interface (Makefile)

```
make esv          → generate.py --edition esv    ; 2-pass build esv_bible.tex
make net-reading  → generate.py --edition net    ; 2-pass build net_reading.tex
make net-notes    → generate.py --edition net    ; 2-pass build net_notes.tex
make geneva       → generate.py --edition geneva ; build geneva_bible.tex (pipeline)
make geneve-1564  → 2-pass build geneve_1564.tex (no generation)
make all          → esv, net-reading, net-notes, geneva, geneve-1564
```

`net-reading` and `net-notes` share the `livres_net/` generation (built once if
current). LuaLaTeX invocation matches today's: `OSFONTDIR=fonts
TEXINPUTS=microtype: lualatex -shell-escape`.

## Migration (approach A — clean copy + archive tags)

All work on `chore/consolidate-editions`, verified, then merged to `master`.

1. **Archive history:** tag `archive/net-notes` = `feature/net-notes` tip and
   `archive/geneva-annotations` = `feature/geneva-annotations` tip; push tags.
   Nothing is lost.
2. **Gather edition files** onto the branch (copy from the archived branch tips):
   - `net_notes.tex`; net-notes cover/index → `editions/net_notes/`
   - geneva `net_bible.tex` → `geneva_bible.tex`; geneva cover/index →
     `editions/geneva/`; annotation scripts + tests + `conftest.py`; annotation
     data JSON → `data/`
   - master `net_bible.tex` → `net_reading.tex`; `livres_esv/cover.tex` →
     `editions/esv/cover.tex`
3. **Populate `editions/<name>/`** with each edition's current hand-crafted
   `cover.tex` + `color_index.tex`.
4. **Rewire `\input` paths** in each main doc to the new asset + generated dirs.
5. **Write `generate.py`**; repoint test files; **new Makefile**.
6. **`.gitignore`:** add `livres_net/`, `livres_geneva/`; keep `livres_esv/`.
7. **Cleanup after merge:** `git worktree remove` both worktrees; delete the
   feature branches (history retained in archive tags).

## Verification

- `generate.py --edition all` runs **offline from caches** and produces book
  files for esv / net / geneva.
- **Byte-equivalence:** regenerated `esv` and `net` book `.tex` are
  diff-identical to the pre-migration files; `geneva` annotated output matches
  its archived version.
- `make all` builds every edition with 0 errors; page counts match baselines
  (ESV 1316, net_notes 2083, geneva ~2002; net_reading and geneve_1564 recorded
  as new baselines).
- All Python tests pass: red-letter, LaTeX escaping, annotation fetcher,
  LaTeX annotations, overlap detector.
- End state: single clean `master`; worktrees removed; archive tags pushed.

## Risks

1. **geneva pipeline orchestration.** Folding `build_annotated.py`'s multi-pass
   overlap/correction flow behind `generate.py --edition geneva` is the most
   complex piece. Mitigation: orchestrate (call the existing functions), don't
   rewrite; verify annotated output matches the archived geneva build.
2. **`\input` path rewiring.** Every main doc's cover/index/book paths change.
   Mitigation: per-edition build verification catches a missed path immediately.
3. **color_index reconciliation.** Each edition's committed `color_index.tex`
   is the source of truth (tracked); `generate.py` does not regenerate it.
   net-notes' is hand-edited, geneva's matches `{wisdom,acts}` — both preserved
   as-is by tracking.
4. **Cache completeness.** `net-notes`' own cache is partial (139); the full
   1189-chapter `net_bible_cache` (master/geneva) is used for `net` generation.

## Out of scope

- Re-typesetting or content changes to any edition.
- Adding verse-number protrusion to the NET editions (separate future task).
- Changing the annotation pipeline's algorithm.
