# PDF Bookmarks (book → chapter outline) — Design

**Date:** 2026-06-08
**Branch:** master
**Status:** Approved design

## Goal

Add a PDF outline (bookmark pane) to the four scripture editions: a top-level
bookmark per book, with a nested sub-bookmark per chapter that jumps directly
to that chapter. This is **in addition to** the existing in-PDF table-of-contents
pages (which are unchanged).

## Approach

Reuse the named destinations the generators already emit — `\hypertarget{book-<dir>}`
(per book, inside the `\bbook` macro) and `\hypertarget{ch-<dir>-<N>}` (per chapter,
at each `\ch{N}`). Load the `bookmark` package and emit `\bookmark[dest=…]`
commands that point at those existing destinations. Because they reference
existing anchors and `\bookmark` is a zero-width whatsit, **nothing in the
typeset layout shifts** — critical for the geneva edition, whose margin-note
overlap convergence must stay intact.

Rejected alternative: `\pdfbookmark` (hyperref-native, no extra package) — also
viable, but it creates a *new* destination at the emit point. Using the existing
anchors via the `bookmark` package is cleaner and decoupled, and the package is
the modern, robust way to build outlines.

## Components

### Main documents (preamble)
Add `\usepackage{bookmark}` immediately after the existing
`\usepackage[hidelinks]{hyperref}` in: `esv_bible.tex`, `net_reading.tex`,
`net_notes.tex`, `geneva_bible.tex`. (Not `geneve_1564.tex` — see Scope.)

### Generators (emit the bookmark commands)
In `scripts/latex_generator.py` (NET) and `scripts/esv_latex_generator.py` (ESV),
inside `generate_book_tex`:
- **Book (level 0):** right after the `\bbook{…}{<dir>}` line, emit
  `\bookmark[dest={book-<dir>},level=0]{<Book Name>}` — e.g. top-level `Genesis`.
- **Chapter (level 1):** at each chapter start (the `verse_num == 1` branch,
  immediately before the `\ch{N}` line), emit
  `\bookmark[dest={ch-<dir>-<N>},level=1]{<Book Name> <N>}` — e.g. nested
  `Genesis 1`, `Genesis 2`, …

Labels: book = `book.name`; chapter = `f"{book.name} {N}"` (e.g. "Genesis 1").
Book names are plain ASCII (e.g. "1 Corinthians", "Song of Solomon") — no
PDF-string escaping needed. Emission is in reading order, so the outline nests
book → its chapters automatically (the `bookmark` package derives nesting from
`level`).

## Scope

- **In:** the four scripture editions (esv, net_reading, net_notes, geneva),
  all driven by the two generators above.
- **Out:** `geneve_1564.tex` (French legacy, 2 pages, different `livres/genese`
  structure, not produced by these generators). Could be added by hand later.
- The existing ToC pages are untouched.

## Verification

- Rebuild each of the four scripture editions.
- Dump each PDF outline (e.g. `mutool show <pdf> outline`, or a PyMuPDF
  `doc.get_toc()`) and confirm: every book is a top-level entry; each book's
  chapters are nested beneath it as `<Book> <N>`; a spot-checked entry jumps to
  the correct page.
- **Zero-layout invariant:** page counts must be unchanged vs current
  (esv 1316, net_reading 1360, net_notes 2078, geneva 2007).
- **Geneva safety:** after regenerating + rebuilding geneva, residual margin-note
  overlaps must remain **0** (the bookmark whatsits must not perturb layout).

## Risks

1. **Geneva layout perturbation.** Mitigated by using zero-width `\bookmark`
   whatsits pointing at existing anchors; verified by the page-count and
   overlap-count checks. If geneva page count changes, stop and investigate.
2. **Single vs two-pass.** `\bookmark[dest=name]` references hyperref named
   destinations; build two passes to be safe so all destinations resolve.
