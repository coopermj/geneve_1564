# How this project relates to scripture.sty

An inventory of what is *inside* the (local) scripture.sty, what merely
*configures* it, and what works *around* it. Written 2026-07-19, at the
v2.3-based local copy.

## Layer 1 — Modifications to scripture.sty itself: ONE 9-line patch

`__scripture_insert_verse_mark:` gets `\mode_if_vertical:T { \penalty 10000 }`
after its `\mark_insert:nn`, binding a vertical-mode (chapter-start) running-
head mark to the material it labels. Without it, the glue after the mark node
is a legal column breakpoint even behind a `\nobreak` — which both orphans a
preceding section heading at the column foot and mislabels the running heads
(the mark ships on the previous column).

- Marked with a `LOCAL PATCH (geneve_1564, 2026-07-17)` comment in the file.
- **Upgrade duty**: re-apply when rebuilding scripture.sty from a new
  upstream tag (dcpurton/scripture). Candidate for an upstream report.

## Layer 2 — Configuration through the documented API (not overrides)

Everything set via `\scripturesetup` in each edition preamble: the grid
skips (`chapter/para/aboveskip`, `poetry/aboveskip`/`belowskip` = `\gridunit`),
`verse/format=\verseprotrudenum{#1}` (OpenType superior figures +
microtype protrusion), `verse/sep`/`poetry/verse/sep=0.3em`,
`chapter/drop=false` + `chapter/para=true` + chapter font/format,
`poetry/bigindent`, `verse/first=false`, `redletter`. Survives upgrades as
long as the public API is stable (held from 2.1 through 2.3).

## Layer 3 — Workarounds AROUND scripture (preambles + generators)

Compensate for scripture's internals or its interactions with other
packages, without touching its code:

- **Heading-orphan guards**: `\nobreak` re-armed after `\bookmark` whatsits
  and paragraph-initial `\markboth` marks; `\headingkeep`/`\headingkeepoff`
  neutralize scripture's list-boundary penalties (`±\@lowpenalty` = ±51)
  around heading+chapter clusters; `\needspace` reserves. Scripture has its
  own `\heading` command — unused here; headings are generator-emitted.
- **The lettrine ecosystem**: scripture has no drop-cap support. The
  `lettrine` package rides alongside; the `\everypar{}`/`\parshape=0`
  emission pattern breaks the recursion between lettrine's `\everypar` and
  scripture's `\Llist@everypar`; the zone-guard system (in-zone paragraph
  merge, poetry flattening, visible-char budgets, `\Needspace*` ghost
  reserves, retro-shrink of `[lines=N]`) manages the interaction
  generator-side. See docs/typography-recommendations.md.
- **Per-verse `\markboth`**: generators emit a LaTeX 2e mark for every verse
  to drive the running heads (`\rightmark`/`\leftmark` = first/last verse on
  the page).

## Layer 4 — Fully scripture-independent typography

Baseline grid (`\gridunit`, pinned `\textheight`), `\lineskiplimit=-1pt`,
lua-widow-control (its three patches live in the project-root
`lua-widow-control.lua`, not in scripture), microtype verse-number
protrusion (`verse_protrusion.tex`), marginnote/footnote systems (geneva),
page geometry, covers, `\bbook` openers.

## Known simplification opportunity (→ feature branch)

Scripture v2.3 added ltmarks-based mark classes (`scripture/verse`,
`scripture/heading`) with a configurable `mark/verse/format` — the very
"Book Ch:V" content our headers need. They fire only when the `book=` key
is set, which the generators never do, so today they are dormant while the
generators duplicate the same information as thousands of `\markboth`
calls. Driving the running heads natively (`\FirstMark{scripture/verse}` /
`\LastMark{scripture/verse}` in the page style, `book=` set per book) would
remove all per-verse `\markboth` emissions AND the mark-node complications
that caused two of the heading-orphan mechanisms and one lua-widow-control
crash. Layer-3 guards tied to `\markboth` become dead code to delete.
