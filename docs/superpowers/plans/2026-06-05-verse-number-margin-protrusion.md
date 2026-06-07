# Verse-Number Margin Protrusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a verse number that lands at the start of a typeset line hang a tuned partial amount into the left margin via microtype protrusion, while mid-line numbers stay inline exactly as today.

**Architecture:** A self-contained, edition-portable preamble file (`verse_protrusion.tex`) defines a verse-number formatter wired into the scripture package's `verse/format` hook. The formatter typesets the number as real OpenType superior-figure glyphs inside a dedicated microtype protrusion context; microtype hangs those glyphs into the margin only when they fall at a line edge. The file feature-detects superior figures (by glyph-width measurement) and falls back to today's `\textsuperscript` on fonts that lack them, so it never breaks and never hardcodes a font.

**Tech Stack:** LuaLaTeX, fontspec, microtype (v3.2d), the `scripture` package (v2.3), `pdftoppm` for visual verification.

---

## Background the engineer must know

- **Build command** (from repo root, this is how `esv_bible.tex` compiles):
  ```bash
  OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=nonstopmode esv_bible.tex
  ```
  A full ESV build is ~1321 pages and slow. For the dev loop, use the small fixture in Task 1, **not** the full book.
- **Why superior figures, not `\textsuperscript`:** microtype protrusion only acts on *glyph* nodes. `\textsuperscript` produces a *raised box*, which microtype cannot protrude. OpenType superior figures (`VerticalPosition=Superior`, i.e. the `sups` feature) are real glyphs microtype can hang. Verified in spikes: microtype left-protrusion fires on the leading glyph of continuation lines in this setup.
- **Font-agnostic rule:** do NOT name "EB Garamond" anywhere in the code. Use `\addfontfeature{VerticalPosition=Superior}` on whatever the current body font is.
- **scripture hook:** verse numbers are formatted by the value of the `verse/format` option (currently `\textsuperscript{#1}`, set in `esv_bible.tex:87`). We change it to call our formatter.
- **Visual verification helper** (used throughout):
  ```bash
  pdftoppm -png -r 220 <file>.pdf /tmp/vp_out && echo /tmp/vp_out-1.png
  ```
  Then open/read `/tmp/vp_out-1.png` and compare the leading verse-number digit's left edge against the column's left edge (a `\rule` baseline marker is included in the fixture).

---

## File Structure

- **Create `verse_protrusion.tex`** (repo root) — the entire feature: verse-number font feature, detection boolean, `\SetProtrusion` set, `\verseprotrudenum` formatter, manual override switch. One responsibility: verse-number protrusion. Edition-portable (`\input` it from any edition's preamble).
- **Create `tests/verse_protrusion_visual_check.tex`** — standalone narrow-column fixture that forces verse numbers to line starts for visual QA (mirrors the existing `tests/redletter_visual_check.tex` pattern).
- **Modify `esv_bible.tex`** — `\input{verse_protrusion}` after microtype + scripture are loaded; change `verse/format` to use `\verseprotrudenum`.

---

## Task 1: Visual-check fixture (the "test")

**Files:**
- Create: `tests/verse_protrusion_visual_check.tex`

- [ ] **Step 1: Write the fixture.** It deliberately `\input`s the not-yet-existing `verse_protrusion.tex` (so it fails first), loads the same toolchain as the book, sets a narrow `\linewidth`, and forces verse numbers to line starts. A `\rule` marks the true column edge so protrusion is visible.

Create `tests/verse_protrusion_visual_check.tex`:

```latex
\documentclass[11pt]{article}
\usepackage{fontspec}
\setmainfont{EB Garamond}[
  Path=../fonts/, Extension=.otf,
  UprightFont=EBGaramond-Regular,
  ItalicFont=EBGaramond-Italic,
  BoldFont=EBGaramond-Bold,
  BoldItalicFont=EBGaramond-BoldItalic,
]
\usepackage[protrusion=true,expansion=true,final]{microtype}
\usepackage{scripture}
\input{../verse_protrusion}
\scripturesetup{
  verse/format=\verseprotrudenum{#1},
  verse/sep=0.1em,
  verse/first=false,
  indent=true,
}
\begin{document}
\parindent=0pt
\setlength{\columnwidth}{45mm}\setlength{\hsize}{45mm}\linewidth=45mm
\noindent\rule{45mm}{0.4pt}\par
\begin{scripture}
% Filler so the next verse number is pushed to the START of a fresh line:
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
\vs{12}And God said, Let there be light, and there was light, and God
saw that the light was good and he divided the light from the darkness.
\vs{13}And the evening and the morning were the first day, and it was so
ordered by the word of his power forever and ever amen.
\end{scripture}
\noindent\rule{45mm}{0.4pt}\par
\end{document}
```

- [ ] **Step 2: Run it to verify it fails (file not found).**

Run:
```bash
tests/build_visual_check.sh
```
Expected: FAIL with `! LaTeX Error: File 'verse_protrusion.tex' not found` (or `\input` cannot find it). This confirms the fixture is wired to our file.

- [ ] **Step 3: Commit the fixture.**

```bash
git add tests/verse_protrusion_visual_check.tex
git commit -m "test: add verse-number protrusion visual-check fixture"
```

---

## Task 2: Implement `verse_protrusion.tex` and make the digit hang

This task contains the main feasibility risk (the `\SetProtrusion`/`\microtypecontext` selector). Implement the file, then iterate using the fixture render until a line-start verse number visibly hangs a *partial* amount into the margin.

**Files:**
- Create: `verse_protrusion.tex`

- [ ] **Step 1: Write `verse_protrusion.tex`.**

Create `verse_protrusion.tex` (repo root):

```latex
%% verse_protrusion.tex
%% Microtype protrusion for verse numbers (edition-portable).
%% Requires, loaded BEFORE this file: fontspec (main font set), microtype, scripture.
%% Effect: a verse number at the start of a line hangs a tuned partial amount
%% into the left margin. Mid-line numbers are unaffected (microtype only
%% protrudes line-edge glyphs). Font-agnostic: uses OpenType superior figures
%% of the CURRENT body font; falls back to \textsuperscript if unavailable.
\makeatletter

% --- Tunable: partial left-protrusion factor (out of 1000 = one glyph width).
\def\verseprot@factor{350}

% --- Manual override (an edition may force the feature off):
\newif\ifverseprotrusion  \verseprotrusiontrue

% --- Named microtype protrusion set: left-only hang on digits 0-9.
%     Activated ONLY inside \verseprotrudenum via \microtypecontext, so no
%     other text is affected.
\SetProtrusion
  [ name = verseprot ]
  { }
  { 0 = {\verseprot@factor}{} , 1 = {\verseprot@factor}{} ,
    2 = {\verseprot@factor}{} , 3 = {\verseprot@factor}{} ,
    4 = {\verseprot@factor}{} , 5 = {\verseprot@factor}{} ,
    6 = {\verseprot@factor}{} , 7 = {\verseprot@factor}{} ,
    8 = {\verseprot@factor}{} , 9 = {\verseprot@factor}{} }

% --- Feature detection (by glyph-width measurement) + final decision.
%     Done at begin-document when the real body font is active.
\newif\ifverseprot@use
\AtBeginDocument{%
  \setbox0=\hbox{{\addfontfeature{VerticalPosition=Superior}0}}%
  \setbox2=\hbox{0}%
  \ifdim\wd0=\wd2 % no substitution happened -> font lacks superior figures
    \verseprot@usefalse
  \else
    \ifverseprotrusion \verseprot@usetrue \else \verseprot@usefalse \fi
  \fi
}

% --- The formatter wired into scripture's verse/format.
\NewDocumentCommand\verseprotrudenum{m}{%
  \ifverseprot@use
    {\addfontfeature{VerticalPosition=Superior}%
     \microtypecontext{protrusion=verseprot}#1}%
  \else
    \textsuperscript{#1}%
  \fi
}

\makeatother
```

- [ ] **Step 2: Render the fixture.**

Run:
```bash
tests/build_visual_check.sh
pdftoppm -png -r 220 tests/verse_protrusion_visual_check.pdf /tmp/vp_out && echo /tmp/vp_out-1.png
```
Then read `/tmp/vp_out-1.png`.

Expected (PASS): the verse number that begins the second line of the block (e.g. `12...` after the `xxxx` filler line) is set as small raised superior figures, and its left edge sits **left of** the `\rule`/column edge by a small partial amount. Mid-line numbers (e.g. `13`) sit inline, not in the margin.

- [ ] **Step 3: If the digit does NOT hang, debug the selector (spike loop).**

The protrusion mechanism is confirmed to work in this setup; if the factor isn't applying, it is the `\SetProtrusion`/context pairing. Try, in order, re-rendering after each change:

1. Add `verbose=true` to the fixture's `microtype` options and check `verse_protrusion_visual_check.log` for `Loading protrusion list verseprot` when the context activates. If absent, the named set isn't being selected.
2. Replace the empty font set `{ }` with an explicit all-font selector:
   `{ font = */*/*/* }`.
3. If superior glyphs are not protruded but plain digits are (risk: protrusion keyed on input codepoint vs substituted glyph), set the factor on the substituted glyphs by name instead — render `\showoutput` is overkill; instead try keying protrusion via the `\SetProtrusion` `inputenc`-independent form by raising the factor temporarily to `900` to confirm direction, then restore.
4. Temporarily raise `\verseprot@factor` to `900` to make any movement obvious while debugging, then restore to `350`.
5. If the build errors at `\SetProtrusion` itself (microtype may not expand `\verseprot@factor` inside the protrusion-value braces), inline the literal number in all ten entries — e.g. `0 = {350}{}` — and drop the `\verseprot@factor` macro from the `\SetProtrusion` call (Task 6 then tunes by editing those literals, or reintroduce the macro with `\number\verseprot@factor`).

Document the working incantation in a comment at the top of `verse_protrusion.tex`.

- [ ] **Step 4: Confirm mid-line numbers are unaffected.** In the same render, verify a verse number that is NOT at a line start sits inline (no margin hang). This is automatic with microtype but must be visually confirmed.

- [ ] **Step 5: Commit.**

```bash
git add verse_protrusion.tex
git commit -m "feat: verse-number margin protrusion via microtype superior figures"
```

---

## Task 3: Wire into `esv_bible.tex`

**Files:**
- Modify: `esv_bible.tex` (add `\input`; change `verse/format`)

- [ ] **Step 1: Add the `\input` after scripture is loaded.** In `esv_bible.tex`, the line `\usepackage{scripture}` is at line 79 and the `\scripturesetup{` block begins at line 80. Insert the input between them.

Change:
```latex
% Scripture package for verse/chapter markup
\usepackage{scripture}
\scripturesetup{
```
to:
```latex
% Scripture package for verse/chapter markup
\usepackage{scripture}
\input{verse_protrusion}
\scripturesetup{
```

- [ ] **Step 2: Change `verse/format` to use the formatter.** In the same `\scripturesetup` block, `esv_bible.tex:87` reads:
```latex
  verse/format=\textsuperscript{#1},
```
Change it to:
```latex
  verse/format=\verseprotrudenum{#1},
```

- [ ] **Step 3: Commit.**

```bash
git add esv_bible.tex
git commit -m "feat: wire verse protrusion into esv_bible.tex"
```

---

## Task 4: Full-book build verification

**Files:** none (verification only)

- [ ] **Step 1: Build the full ESV book.**

Run (slow; ~1321 pages):
```bash
rm -f esv_bible.aux esv_bible.toc esv_bible.out
OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=nonstopmode esv_bible.tex > /tmp/esv_p1.log 2>&1
OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=nonstopmode esv_bible.tex > /tmp/esv_p2.log 2>&1
echo "errors:"; grep -iE "^!|Undefined control|Fatal|Emergency" esv_bible.log | head
echo "pages:"; grep -oE "Output written.*page" esv_bible.log | tail -1
```
Expected: 0 errors; `Output written on esv_bible.pdf (1321 pages...` (page count may shift by ≤1–2 if line breaks move; flag if it changes by more).

- [ ] **Step 2: Visual spot-check a real page.** Pick a text-heavy page and render it:
```bash
pdftoppm -png -r 200 -f 30 -l 31 esv_bible.pdf /tmp/esv_pg && echo /tmp/esv_pg-30.png
```
Read the PNG. Expected: superior-figure verse numbers throughout; any number that begins a line hangs slightly into the margin/gutter; body-text left edges look clean; no numbers awkwardly far into the column gap.

- [ ] **Step 3: Commit nothing (verification only). If page count or layout regressed unacceptably, return to Task 2 Step 3 / tune factor in Task 6.**

---

## Task 5: Fallback verification (font without superior figures)

**Files:** none (verification only; temporary edit reverted)

- [ ] **Step 1: Force the fallback path and confirm graceful degradation.** Temporarily add, in `tests/verse_protrusion_visual_check.tex` right after `\input{../verse_protrusion}`:
```latex
\verseprotrusionfalse
```
Render:
```bash
tests/build_visual_check.sh
pdftoppm -png -r 220 tests/verse_protrusion_visual_check.pdf /tmp/vp_fb && echo /tmp/vp_fb-1.png
```
Read the PNG. Expected: verse numbers render as ordinary `\textsuperscript` (no margin hang, no superior-figure styling) — i.e. today's behavior, no errors.

- [ ] **Step 2: Revert the temporary edit.**
```bash
git checkout tests/verse_protrusion_visual_check.tex
```

---

## Task 6: Tune the protrusion factor and finalize

**Files:**
- Modify: `verse_protrusion.tex` (only `\verseprot@factor` if needed)

- [ ] **Step 1: Optically tune.** From the Task 4 Step 2 page render, judge the hang. If too subtle, raise `\verseprot@factor` (e.g. to `450`); if too far into the gutter, lower it (e.g. to `250`). Edit only:
```latex
\def\verseprot@factor{350}
```

- [ ] **Step 2: Re-render the fixture to confirm the new factor.**
```bash
tests/build_visual_check.sh
pdftoppm -png -r 220 tests/verse_protrusion_visual_check.pdf /tmp/vp_tune && echo /tmp/vp_tune-1.png
```
Read the PNG and confirm the hang looks right.

- [ ] **Step 3: Commit if the factor changed.**
```bash
git add verse_protrusion.tex
git commit -m "tune: verse protrusion factor"
```

---

## Self-review notes

- **Spec coverage:** behavior/trigger/partial-amount (Tasks 1–2, 6), microtype mechanism (Task 2), font-agnostic + graceful fallback (Task 2 detection, Task 5), scripture hooks (`verse/format` in Task 3), portability (`verse_protrusion.tex` is `\input`-able), verification incl. two-column gutter spot-check (Task 4) and mid-line-unchanged (Task 2 Step 4) — all covered.
- **Risk register from spec:** SetProtrusion/context pairing → Task 2 Step 3 spike loop; GSUB-substituted-glyph protrusion → Task 2 Step 3 item 3; two-column gutter → Task 4 Step 2 + Task 6 tuning; lettrine/red-letter interaction → Task 4 full build surfaces any error (verse 1 prints no number, so chapter openings are unaffected).
- **Known approximation:** "tests" are visual (render + inspect PNG), not automated asserts — appropriate for typographic output; expected visual outcomes are stated explicitly per step.
```
