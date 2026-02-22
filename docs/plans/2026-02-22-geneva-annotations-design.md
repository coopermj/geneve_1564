# Geneva Annotations / Marginal Notes — Design

**Date:** 2026-02-22
**Approach:** Python compile → scan → iterate (Approach B)

---

## Goal

Add 1599 Geneva Bible marginal annotations to the NET Bible PDF, matching the original Geneva Bible aesthetic: superscript letter markers inline in the text, corresponding notes in the outer margin.

---

## Data Layer

**Source:** StudyLight
URL pattern: `https://studylight.org/commentaries/eng/gsb/{book-name}-{chapter}.html`

**New script:** `scripts/annotation_fetcher.py`
- Iterates all 66 books × all chapters
- Parses HTML to extract verse number, letter labels `(a)`, `(b)`..., and annotation text
- Caches per-chapter HTML to `data/annotations_cache/` to avoid re-scraping
- Outputs `data/geneva_annotations.json`

**JSON format:**
```json
{
  "genesis": {
    "1": {
      "1": [{"letter": "a", "text": "First of all, before any creature was..."}],
      "2": [
        {"letter": "b", "text": "An unformed lump..."},
        {"letter": "c", "text": "..."}
      ]
    }
  }
}
```

**Note:** Since annotation letters are keyed to specific words in the 1599 Geneva text (not the NET Bible), word-level alignment is not possible. Inline markers are clustered at the end of each verse.

---

## LaTeX Integration

**New command:**
```latex
\newcommand{\gva}[1]{\textsuperscript{\scriptsize\textit{#1}}}
```

**Package:** `\usepackage{marginnote}` added to `net_bible.tex`. Handles recto/verso outer margin placement automatically.

**Emitted per annotated verse:**
```latex
...verse text\gva{a}\marginnote{\gva{a}\,Annotation text.}\gva{b}\marginnote{\gva{b}\,Annotation text.}  % GVA:genesis:1:1:a
```

Each `\marginnote` gets a unique label comment `% GVA:{book}:{chapter}:{verse}:{letter}` for offset patching.

**`latex_generator.py` changes:** After converting verse HTML to LaTeX, append the annotation cluster by looking up `annotations[book][chapter][verse]`.

**Geometry:** Uses existing outer margin — no page geometry changes.

---

## Overlap Detection & Iteration Loop

**New script:** `scripts/overlap_detector.py`
- Uses PyMuPDF (`fitz`) to extract bounding boxes of all text on each page
- Identifies margin notes by x-position falling in the outer margin zone
- Walks consecutive margin note boxes sorted by top-y; flags overlaps where `box[i].y1 > box[i+1].y0`
- Returns correction map: `{(page, note_label): offset_pt}`

**New script:** `scripts/build_annotated.py` — orchestrates the full build loop:
```
for iteration in range(MAX_ITER=3):
    lualatex net_bible.tex
    corrections = overlap_detector.detect("net_bible.pdf")
    if not corrections:
        break
    latex_generator.apply_offsets(corrections)
```

**Fallback:** Any note still overlapping after 3 iterations is demoted to `\footnote`. The inline `\gva{x}` marker remains in the text.

---

## New Files

| File | Purpose |
|------|---------|
| `scripts/annotation_fetcher.py` | Scrape & cache Geneva annotations from StudyLight |
| `scripts/overlap_detector.py` | PyMuPDF-based margin note overlap detection |
| `scripts/build_annotated.py` | Compile → detect → patch → recompile loop |
| `data/geneva_annotations.json` | Scraped annotation data |
| `data/annotations_cache/` | Per-chapter HTML cache |

## Modified Files

| File | Change |
|------|--------|
| `scripts/latex_generator.py` | Inject `\gva` markers and `\marginnote` calls; `apply_offsets()` method |
| `net_bible.tex` | Add `marginnote` package, `\gva` command |
| `scripts/requirements.txt` | Add `pymupdf`, `beautifulsoup4` |
| `Makefile` | Add `annotate` and `build-annotated` targets |
