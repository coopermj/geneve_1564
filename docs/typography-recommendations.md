# Typography Recommendations — ESV Bible Edition (esv_bible.tex)

Review of `scripture.sty` (v2.3) and `esv_bible.tex`, 2026-07-15.
Recommendations for a PDF edition of scripture following best and historic
design practices (Geneva 1560/64, KJV 1611, Doves Bible, Bruce Rogers'
Oxford Lectern Bible, Tschichold, Bringhurst).

## Already excellent (do not regress)

- Hanging verse numbers: OpenType superior figures + tuned microtype
  protrusion (`verse_protrusion.tex`) — the LuaTeX equivalent of Bruce
  Rogers' optical margin work.
- Hanging punctuation via `\SetProtrusion[load=default]` (Gutenberg 42-line
  Bible practice).
- Old-style figures body-wide; discretionary ct/st ligatures (`+dlig`).
- Letterspaced small caps for display only (never lowercase) — Bringhurst.
- `\textsc{Lord}` for the Tetragrammaton.
- Verse-content running heads via per-verse `\markboth`: `\rightmark` =
  first verse on page (inner head), `\leftmark` = last verse (outer head) —
  the historic content-range convention.
- `verse/first=false` with lettrine standing for verse 1.
- Fixed (non-stretchable) verse-number separation: `verse/sep=0.3em`,
  `poetry/verse/sep=0.3em`, generator emits `\vs{N}text` with no space.

## Implementation status (2026-07-17)

Items 1 and 2 are implemented across ALL FOUR editions. Per-edition grid
numbers (gridunit == \baselineskip, sp-exact; textheight pinned to
\topskip + N·gridunit so \flushbottom never stretches):

| edition       | body        | gridunit          | N  | lines/col |
|---------------|-------------|-------------------|----|-----------|
| esv_bible     | 11pt ×0.9   | 12.23991pt        | 45 | 46        |
| net_reading   | 11pt ×0.9   | 12.23991pt        | 45 | 46        |
| net_notes     | 11.4/14pt   | 14pt (exact)      | 35 | 36        |
| geneva_bible  | 13pt ×0.9   | 920116sp (14.04pt)| 39 | 40        |

Shared mechanics: poetry/aboveskip=belowskip=\gridunit; chapter/para/
aboveskip=\gridunit; \lineskiplimit=-1pt (metric-tall glyphs — opening
quotes, superior figures — may graze the baseline distance; ink never
touches); \bbook opener boxed in \bbookheadbox and padded to the next
whole gridunit multiple (ceil via rounding division in \numexpr).

**Heading-orphan mechanism (ESV only — NET source has no headings).** A
heading's \nobreak can be defeated three separate ways, each needing its own
guard (all in esv_latex_generator.py / esv_bible.tex):
1. `\bookmark` whatsit after the heading → glue after a non-discardable node
   is breakable again → emit `\nobreak` after the bookmark.
2. Paragraph-initial `\markboth` (mark node) → same — inject `\nobreak`
   after the mark.
3. scripture's inner LIST environments set \@endparpenalty=\@lowpenalty(51)
   and \@beginparpenalty=-51; the list end/begin at a poetry chapter
   boundary inserts those penalty NODES after ours (consecutive penalties do
   not merge — each is an independent breakpoint) → `\headingkeep` /
   `\headingkeepoff` neutralize them around the heading+next block.
Also: lua-widow-control's move_last_line orphaned headings when a mark node
broke its heading-detection walk (patched, see below). Catch-all leg:
`\needspace{5\gridunit}` before each heading (reserves room for
heading + superscription + chapter + first verse). Net result 41 → 4
orphans over 1340pp; the residual 4 shift with any reflow (at least one
more breakable seam exists inside scripture's poetry chapter machinery —
diagnose with `\tracingpages=1`; a p=0 break at exact goal height is the
signature). Scanner: `check_heading_orphans.py` (scratchpad); the
`'1'`-text hits are chapter-table digit false positives.

**lua-widow-control v3.0.1 patches** (project-root `lua-widow-control.lua`
is canonical — kpse resolves it ahead of any installed tree; a copy is also
patched in the TinyTeX tree):
1. move_last_line crashed on trailing mark nodes ("cannot set field list in
   a node of type mark") — walk back to the last hlist.
2. first_last_paragraphs crashed on abs(nil) when no paragraph on the page
   carries the attribute — guard and bail.
3. Heading-detection walk treated mark/whatsit/kern as "not found",
   moving the lone line and stranding the heading — made them transparent
   like glue.

**Poetry classification fix**: `poetry_sections.json` had `full_book: true`
for Hosea and Malachi; ESV source line-span data shows Hosea 1+3 and ALL of
Malachi are prose. Now `hosea: chapters [[2,2],[4,14]]`, malachi removed.
Audit method: count `class="...line..."` spans per chapter in
`data/esv_cache/` — 0 spans = prose chapter.

**Known accepted artifact**: a prose chapter's 5-line lettrine block is
unbreakable; when it lands near a column foot TeX carries it whole to the
next column, leaving a short column (raggedbottom absorbs it silently).
This is the historically accepted trade — never stretch the grid to fill.

## 1. Baseline grid (IMPLEMENTED 2026-07-15)

The single biggest upgrade for two-column scripture: line-for-line register
between columns, and (for print) backup register across the leaf.

- Replace `\linespread{0.9}` (opaque multiplier → 12.24pt leading) with an
  explicit grid unit, and make text height exactly
  `\topskip + N·\baselineskip` so `\flushbottom` never stretches.
- Italic section headings were emitted as
  `\vspace{\baselineskip}\noindent{\small\itshape …\par}` — the `\par`
  inside the `\small` group gives the heading line `\small`'s baselineskip
  (≈10.8pt), knocking columns out of register. Fix: close the paragraph
  OUTSIDE the size group (`\noindent{\small\itshape …}\strut\par`) so the
  heading occupies exactly one body grid line; with the preceding
  `\vspace{\baselineskip}` the block consumes exactly 2 lines.
- Audit every vertical interval to be a line multiple:
  `chapter/para/aboveskip=\baselineskip`, `belowskip=0pt` (already integral;
  chapter/font has no size change so the chapter line is 1 grid line),
  poetry above/belowskip, stanza skips.
- Book-opening `\twocolumn[…]` inserts have arbitrary height → columns on
  those 66 pages start off-grid and flushbottom stretches. Fix: measure the
  opener in a box and pad its height to the next `\baselineskip` multiple
  (`\gridsnap` logic in `\bbook`).

## 2. lua-widow-control (IMPLEMENTED 2026-07-15)

`\usepackage{lua-widow-control}` — LuaTeX-only: removes widows/orphans by
lengthening/shortening a paragraph via callbacks instead of stretching
vertical space. Grid-safe; nothing in pdfTeX can do this. Do NOT instead set
`\widowpenalty=10000` — in a narrow two-column measure that forces page
stretching and breaks the grid.

## 3. Line-breaking in the narrow measure (TODO)

Columns run ~40–45 characters. Add:

```latex
\tolerance=400 \emergencystretch=.5em
\doublehyphendemerits=7500 \finalhyphendemerits=7500
```

And a hyphenation exception list for biblical proper names (historic house
practice at Oxford/Cambridge): `\hyphenation{Ne-bu-chad-nez-zar
Me-phib-o-sheth Je-hosh-a-phat …}` covering the ~200 hardest names.

## 4. QA tooling (TODO)

- `lua-typo` (Daniel Flipo, LuaLaTeX-only): diagnostic build that colors
  widows, orphans, hyphen ladders, near-rivers. Essential at 1300+ pages.
- Keep the existing PyMuPDF measurement loop (verse-gap stdev, margin-note
  overlap) as regression checks.

## 5. Historic-detail refinements (TODO / optional)

- **Running heads in spaced small caps**: currently `\headerfont\small\upshape`
  roman; historic heads are letterspaced caps/small caps. Consider a range
  form `Genesis 1:2–31`. CAUTION: microtype `tracking=true` letterspaces
  small caps by default — check the manually letterspaced `\booktitlefont`
  (LetterSpace=40) isn't tracked twice; restrict via `\SetTracking` if so.
- **Geneva-authentic chapter style**: `CHAP. I.` — small caps, roman
  numerals, trailing period (one `chapter/format` change).
- **Opening-phrase small caps**: extend beyond `\lettrine{I}{\textsc{n}}` to
  the whole first phrase at book openings (Doves Bible "IN THE BEGINNING").
- **Rubric color**: scripture's default `redletter/colour=red` is harsh;
  deep brick/vermilion `#AE0000` is both historic and eInk-friendly
  (Gallery 3 dithers saturated red).
- **The Argument measure**: `\scriptsize` justified across full 130mm ≈
  100+ chars/line. Bump to `\footnotesize`, narrow to ~0.75\textwidth, or
  set two-column.
- **Margin notes**: `\tiny` (6pt) in 3.5em is at the legibility edge; 7pt
  with a slightly wider `\marginparwidth` if the outer margin allows
  (Geneva-annotations edition settled on 9pt/10.5 in a real margin).
- **Column rule** (only for a KJV-1611 look, not Geneva):
  `\setlength\columnseprule{0.25pt}` + gray rule color. Leave off for the
  Geneva aesthetic.

## 6. If this edition goes to paper (TODO when relevant)

Current `oneside, openany` + home-icon footer targets the Remarkable eInk
device. A print master needs:

- `twoside` with mirrored margins and a real binding gutter (the
  `\areaset[8mm]` correction is per-side).
- Folios restored: spaced small-caps book name + page number in the head.
- Keep `openany` (Bibles traditionally run books in to save bulk).
- Baseline grid pays double on thin paper: verso/recto lines must back each
  other up (show-through).
