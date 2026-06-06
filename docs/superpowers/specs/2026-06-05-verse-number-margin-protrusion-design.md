# Verse-Number Margin Protrusion — Design

**Date:** 2026-06-05
**Branch:** `feature/verse-number-protrusion`
**Status:** Approved design, pending implementation plan

## Goal

Apply the microtype *character-protrusion* concept to verse numbers: when a
verse number falls at the **start of a typeset line**, it hangs a tuned
**partial** amount into the left margin/gutter, keeping the body-text left edge
optically cleaner — analogous to how hanging punctuation (hyphens, quotes)
protrudes. Mid-line verse numbers (the common case) are unchanged.

This is an optical refinement only. It is **not** a layout change that moves all
verse numbers into the margin.

## Requirements (confirmed)

1. **Mechanism:** microtype protrusion (not `\llap`/manual kerning).
2. **Trigger:** only when a verse number lands at the start of a line. Mid-line
   numbers stay inline exactly as today.
3. **Amount:** partial / optical hang (a tuned fraction of the number's width),
   not a full pull-out.
4. **Font-agnostic:** must not assume EB Garamond. Works through whatever main
   font the document uses; degrades gracefully on fonts that lack the needed
   OpenType feature.
5. **Use the scripture package's documented hooks** (`verse/format`,
   `verse/font`, `scripture/verse/before|after`) — not internal redefinitions.

## Feasibility findings (from spikes)

- microtype left-protrusion **does** fire on the leading glyph of continuation
  lines in this project's LuaLaTeX + fontspec setup (verified: a leading curly
  open-quote hangs into the left margin).
- microtype can only protrude **glyph** nodes, **not boxes**. The default
  `verse/format = \textsuperscript{#1}` produces a *raised box*, so the number
  is invisible to protrusion as-is.
- EB Garamond exposes OpenType **superior figures** (`sups` /
  `VerticalPosition=Superior`) — real glyphs that microtype can protrude. Not
  all fonts have this; the design must feature-detect, never hardcode.
- A naive `\SetProtrusion[name=…]` + `\microtypecontext{protrusion=…}` pairing
  silently failed to apply in a spike. Getting the selector right is the first
  implementation step (see Risks).

## Approach (selected: A — microtype + superior figures)

Route verse numbers through scripture's `verse/format` hook as **real
superior-figure glyphs**, and register a tuned **partial left-protrusion** for
those glyphs in a dedicated microtype context. Because protrusion only acts at
line edges, the "only at line start" requirement is satisfied automatically.
Font-agnostic via feature-detection with graceful fallback to today's
`\textsuperscript`.

Rejected alternatives:
- **B — LuaLaTeX node callback** shifting the boxed number at line start.
  Robust and fully font-agnostic, but adds custom Lua and line-break edge
  cases. Kept in reserve as a future fallback for fonts lacking superior
  figures.
- **C — `\llap`/manual kern.** Always protrudes, including mid-line — violates
  requirement 2. Rejected.

## Components

All wiring goes through the scripture package's public options/hooks.

### `\versenumfont`
A verse-number font instance derived from the document's **current main font**
(not a hardcoded family), requesting superior figures via fontspec
`VerticalPosition=Superior` (`+sups`). Keeps the feature font-agnostic.

### `\verseprotrudenum{#1}`
The formatter wired in via `verse/format = \verseprotrudenum{#1}` in
`\scripturesetup`. Branches on detection:
- **Superior figures available** →
  `{\versenumfont \microtypecontext{protrusion=verseprot}#1}`
  (real glyphs, protruded at line start).
- **Not available** → `\textsuperscript{#1}` (today's behavior; boxed, no
  protrusion).

### `verseprot` protrusion set
`\SetProtrusion[name=verseprot]{<selector>}{ 0–9 = {<factor>}{} }` — left-only
(right protrusion empty), **partial** factor. Activated *only* around the verse
number via `\microtypecontext{protrusion=verseprot}` so nothing else in the
text is affected.

### Tunable factor
The protrusion factor is a single source-of-truth macro (starting value ~`350`
out of 1000, i.e. ~0.35 of the glyph width) so it can be optically tuned by
recompiling and eyeballing.

## Font-agnostic detection & fallback

- Detection: a small luaotfload feature query for `sups` in the current font.
- Manual override: `\verseprotrusiontrue` / `\verseprotrusionfalse` so any
  edition can force the feature off regardless of detection.
- Fallback behavior: when superior figures are absent (or the override is off),
  `\verseprotrudenum` reproduces today's `\textsuperscript{#1}` exactly — the
  build never breaks; it simply does not hang.

## Scope & integration

- Packaged as a **self-contained, edition-portable preamble block**: the font
  instance, `\SetProtrusion`, `\verseprotrudenum`, the detection/override
  switch, and the `verse/format` setting.
- Initially wired into **`esv_bible.tex`** (master/current branch), whose
  EB Garamond supplies `sups`.
- Other editions (`net_bible.tex`, `net_notes.tex`, geneva-annotations) can
  `\input` the same block later; each either gets the effect (font permitting)
  or graceful fallback.

## Verification

- **Visual-check fixture** (modeled on `tests/redletter_visual_check.tex`):
  a narrow column that forces verse numbers to line starts, rendered to PNG for
  inspection of the partial hang.
- Rebuild `esv_bible.tex` and confirm:
  - partial hang on line-start verse numbers;
  - **mid-line numbers unchanged**;
  - page count stable (~1321);
  - no new errors/warnings.
- Confirm the graceful-fallback path (force detection off) reproduces today's
  superscript output.

## Risks (to resolve during implementation)

1. **`\SetProtrusion` + `\microtypecontext` pairing.** A spike silently failed
   to apply a named set. First implementation step is a focused spike to nail
   the correct selector/context so the factor actually fires on a leading
   glyph.
2. **Protrusion of GSUB-substituted superior glyphs.** Verify microtype
   protrudes the *substituted* superior figure when the factor is keyed on the
   input digit codepoints; if not, adjust the selector or fall back.
3. **Two-column gutter.** A right-column verse number protrudes left into the
   6 mm `columnsep`. The partial/optical amount keeps this subtle; confirm
   visually and tune.
4. **Interaction with existing workarounds.** Confirm no regression with the
   lettrine/`\everypar` workaround and red-letter (verse numbers remain black).
   Note: `verse/first=false` means verse 1 prints no number, so chapter-opening
   lines are unaffected.

## Out of scope

- Moving all verse numbers into the margin (study-Bible marginal style).
- Hanging-indent verse paragraphs.
- The LuaLaTeX node-callback approach (B) — reserved for a future iteration if
  universal coverage on non-`sups` fonts is needed.
