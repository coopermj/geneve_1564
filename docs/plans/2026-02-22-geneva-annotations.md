# Geneva Annotations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 1599 Geneva Bible marginal annotations to the NET Bible PDF — superscript letter markers inline in verse text, corresponding notes in the outer right margin, with PyMuPDF-based overlap detection and iterative correction.

**Architecture:** Scrape StudyLight's Geneva Study Bible commentary into `data/geneva_annotations.json`, thread annotation data through `latex_generator.py` to emit `\gva{a}\marginnote{...}` clusters after each verse, write a note manifest during generation, then use `build_annotated.py` to compile → detect overlaps → regenerate with offsets → recompile (≤3 iterations, demote to `\footnote` on persistent overlap).

**Tech Stack:** Python 3.13, BeautifulSoup4, PyMuPDF (fitz), LuaLaTeX, marginnote package, pytest

---

## Context: Key Files

- `scripts/latex_generator.py` — HTML→LaTeX converter; `generate_book_tex()` is the core function to modify
- `scripts/generate_bible.py` — CLI entry point that calls `generate_book_tex()` for all 66 books
- `scripts/bible_config.py` — `BOOKS` list with `BookInfo` dataclass (`.directory` slug, `.chapters` count)
- `net_bible.tex` — main LaTeX document, preamble at lines 1–150
- `scripts/requirements.txt` — pip dependencies
- `Makefile` — build targets
- `data/` — project data dir (already exists, stores `net_bible_cache/`, `geneva_arguments.json`)

## StudyLight HTML Structure

URL: `https://www.studylight.org/commentaries/eng/gsb/{slug}-{chapter}.html`

```html
<h3>Verse 1</h3>
<p>1:1 In the <sup>{a}</sup> beginning God created...</p>
<p>(a) First of all, and before any creature was, God made heaven and earth out of nothing.</p>
<h3>Verse 2</h3>
<p>1:2 And the earth was <sup>{b}</sup> without form...</p>
<p>(b) An unformed lump without any creature...</p>
<p>(c) That is, the waters...</p>
```

**Parsing strategy:** find `<h3>Verse N</h3>` elements; collect subsequent `<p>` tags until next `<h3>`; extract annotations whose text matches `^\([a-z]+\)\s+(.+)`.

## URL Slug Mapping

Internal `book.directory` → StudyLight slug:
- Single-word books: identity (`genesis` → `genesis`, `psalms` → `psalms`)
- Numbered books: insert hyphen after digit prefix (`1samuel` → `1-samuel`, `2corinthians` → `2-corinthians`)
- Special case: `songofsolomon` → `song-of-solomon`

Algorithm: `re.sub(r'^(\d+)([a-z])', r'\1-\2', slug)`, then replace `song-of-solomon` special case before the regex.

## Data Format

`data/geneva_annotations.json`:
```json
{
  "genesis": {
    "1": {
      "1": [{"letter": "a", "text": "First of all, and before any creature was..."}],
      "2": [
        {"letter": "b", "text": "An unformed lump..."},
        {"letter": "c", "text": "That is, the waters..."}
      ]
    }
  }
}
```

Keys are strings. Verse keys that have no annotations are absent.

## LaTeX Commands

Added to `net_bible.tex` preamble:
```latex
\usepackage{marginnote}
\newcommand{\gva}[1]{\textsuperscript{\scriptsize\textit{#1}}}
```

`\marginnote` syntax: `\marginnote{text}` (no offset) or `\marginnote[Xpt]{text}` (positive = down).

Generated verse suffix:
```latex
\gva{a}\marginnote{\gva{a}\,First of all...}\gva{b}\marginnote{\gva{b}\,An unformed lump...}
```

With correction offset:
```latex
\gva{a}\marginnote[24.5pt]{\gva{a}\,First of all...}
```

With footnote fallback:
```latex
\gva{a}\footnote{\gva{a}\,First of all...}
```

## Note Manifest

`data/note_manifest.json` — written during `.tex` generation, consumed by overlap detector:
```json
[
  {"idx": 0, "book": "genesis", "ch": 1, "verse": 1, "letter": "a"},
  {"idx": 1, "book": "genesis", "ch": 1, "verse": 2, "letter": "b"},
  ...
]
```

Notes appear in the PDF in the same order as in the manifest (LaTeX processes source top-to-bottom = Genesis→Revelation order).

## Overlap Detection

PyMuPDF page coordinates are in points (1pt = 1/72 inch). Page width ≈ 507pt (179mm). Text block right edge ≈ 436pt. Margin notes identified by x0 > 435.

For each page:
1. Extract text blocks with `page.get_text("dict")["blocks"]`
2. Filter to outer margin zone: `block["bbox"][0] > 435`
3. Sort by y0 (top of bounding box)
4. Walk consecutive pairs: if `bbox[i][3] + GAP > bbox[i+1][1]` → overlap
5. Propagate: push `bbox[i+1]` down by `(bbox[i][3] + GAP) - bbox[i+1][1]`
6. If pushed note bottom `> page_height - BOTTOM_MARGIN` → mark as footnote
7. Return `{manifest_idx: offset_pt}` (or `{manifest_idx: "footnote"}`)

Constants: `GAP = 2.0`, `BOTTOM_MARGIN = 36.0` (0.5 inch)

## generate_book_tex Signature Change

```python
def generate_book_tex(
    book: BookInfo,
    chapters_data: dict[int, list[dict]],
    plan_endpoints: dict | None = None,
    annotations: dict | None = None,       # NEW: {ch_str: {verse_str: [{letter, text}]}}
    corrections: dict | None = None,       # NEW: {manifest_idx: float | "footnote"}
    note_manifest: list | None = None,     # NEW: list to append note records to (mutated)
) -> str:
```

All new parameters default to `None` (backward-compatible). Existing callers in `generate_bible.py` need no changes unless they want annotations.

---

## Task 1: Setup — Dependencies and LaTeX Preamble

**Files:**
- Modify: `scripts/requirements.txt`
- Modify: `net_bible.tex:1-10` (preamble, after `\usepackage{bigfoot}`)
- Create: `tests/` directory and `tests/conftest.py`

**Step 1: Add dependencies to requirements.txt**

Current content:
```
requests
python-dotenv
pdfplumber
```

New content:
```
requests
python-dotenv
pdfplumber
pymupdf
beautifulsoup4
lxml
```

**Step 2: Add marginnote package and \gva command to net_bible.tex**

After line 4 (`\usepackage{bigfoot}`), insert:
```latex
\usepackage{marginnote}
\newcommand{\gva}[1]{\textsuperscript{\scriptsize\textit{#1}}}
```

**Step 3: Install dependencies**

```bash
pip install pymupdf beautifulsoup4 lxml
```
Expected: no errors.

**Step 4: Create tests/ directory with conftest.py**

```python
# tests/conftest.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
```

**Step 5: Verify LaTeX change compiles**

```bash
cd /Users/micahcooper/geneve_1564
OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=batchmode net_bible.tex 2>&1 | tail -5
```
Expected: exit 0, no errors about `marginnote`.

**Step 6: Commit**

```bash
git add scripts/requirements.txt net_bible.tex tests/conftest.py
git commit -m "feat: add marginnote, pymupdf, beautifulsoup4 for Geneva annotations"
```

---

## Task 2: annotation_fetcher.py — Scrape StudyLight

**Files:**
- Create: `scripts/annotation_fetcher.py`
- Create: `tests/test_annotation_fetcher.py`

**Step 1: Write failing tests**

```python
# tests/test_annotation_fetcher.py
import pytest
from annotation_fetcher import _dir_to_slug, parse_chapter_html

GENESIS_1_FIXTURE = """
<html><body>
<h3>Verse 1</h3>
<p>1:1 In the <sup>{a}</sup> beginning God created the heaven and the earth.</p>
<p>(a) First of all, and before any creature was, God made heaven and earth out of nothing.</p>
<h3>Verse 2</h3>
<p>1:2 And the earth was <sup>{b}</sup> without form, and <sup>{c}</sup> void.</p>
<p>(b) An unformed lump without any creature.</p>
<p>(c) That is, the waters covered it.</p>
<h3>Verse 3</h3>
<p>1:3 And God said, Let there be light.</p>
</body></html>
"""


def test_dir_to_slug_simple():
    assert _dir_to_slug("genesis") == "genesis"
    assert _dir_to_slug("psalms") == "psalms"
    assert _dir_to_slug("revelation") == "revelation"


def test_dir_to_slug_numbered():
    assert _dir_to_slug("1samuel") == "1-samuel"
    assert _dir_to_slug("2kings") == "2-kings"
    assert _dir_to_slug("1chronicles") == "1-chronicles"
    assert _dir_to_slug("2corinthians") == "2-corinthians"
    assert _dir_to_slug("1thessalonians") == "1-thessalonians"
    assert _dir_to_slug("3john") == "3-john"


def test_dir_to_slug_song():
    assert _dir_to_slug("songofsolomon") == "song-of-solomon"


def test_parse_chapter_verse1_has_annotation():
    result = parse_chapter_html(GENESIS_1_FIXTURE)
    assert "1" in result
    assert len(result["1"]) == 1
    assert result["1"][0]["letter"] == "a"
    assert "First of all" in result["1"][0]["text"]


def test_parse_chapter_verse2_has_two_annotations():
    result = parse_chapter_html(GENESIS_1_FIXTURE)
    assert len(result["2"]) == 2
    assert result["2"][0]["letter"] == "b"
    assert result["2"][1]["letter"] == "c"


def test_parse_chapter_verse3_no_annotations():
    result = parse_chapter_html(GENESIS_1_FIXTURE)
    assert "3" not in result


def test_parse_chapter_annotation_text_stripped():
    result = parse_chapter_html(GENESIS_1_FIXTURE)
    assert result["1"][0]["text"] == "First of all, and before any creature was, God made heaven and earth out of nothing."
```

**Step 2: Run tests — verify they fail**

```bash
cd /Users/micahcooper/geneve_1564
python -m pytest tests/test_annotation_fetcher.py -v 2>&1 | head -20
```
Expected: `ImportError: No module named 'annotation_fetcher'`

**Step 3: Implement annotation_fetcher.py**

```python
# scripts/annotation_fetcher.py
"""Scrape 1599 Geneva Bible annotations from StudyLight and cache to JSON."""

import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_CACHE_DIR = os.path.join(_PROJECT_ROOT, "data", "annotations_cache")
_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "data", "geneva_annotations.json")
_BASE_URL = "https://www.studylight.org/commentaries/eng/gsb/{slug}-{chapter}.html"
_ANNOTATION_RE = re.compile(r'^\(([a-z]+)\)\s+(.*)', re.DOTALL)


def _dir_to_slug(book_dir: str) -> str:
    """Convert internal book directory slug to StudyLight URL slug."""
    if book_dir == "songofsolomon":
        return "song-of-solomon"
    return re.sub(r'^(\d+)([a-z])', r'\1-\2', book_dir)


def parse_chapter_html(html: str) -> dict[str, list[dict]]:
    """Parse StudyLight chapter HTML into {verse_str: [{letter, text}]}.

    Returns only verses that have at least one annotation.
    Verse numbers that appear in <h3> tags but have no annotation paragraphs
    are omitted from the result.
    """
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, list[dict]] = {}

    # Find all <h3> elements matching "Verse N"
    verse_headers = [
        h for h in soup.find_all("h3")
        if re.match(r'^\s*Verse\s+(\d+)\s*$', h.get_text())
    ]

    for header in verse_headers:
        m = re.match(r'^\s*Verse\s+(\d+)\s*$', header.get_text())
        verse_num = m.group(1)
        annotations = []

        # Collect sibling <p> tags until the next <h3>
        sibling = header.next_sibling
        while sibling is not None:
            if hasattr(sibling, 'name'):
                if sibling.name == 'h3':
                    break
                if sibling.name == 'p':
                    text = sibling.get_text(separator=' ', strip=True)
                    am = _ANNOTATION_RE.match(text)
                    if am:
                        annotations.append({
                            "letter": am.group(1),
                            "text": am.group(2).strip(),
                        })
            sibling = sibling.next_sibling

        if annotations:
            result[verse_num] = annotations

    return result


def _fetch_chapter_html(slug: str, chapter: int) -> str:
    """Fetch chapter HTML, using file cache. Returns empty string on error."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(_CACHE_DIR, f"{slug}-{chapter}.html")

    if os.path.isfile(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    url = _BASE_URL.format(slug=slug, chapter=chapter)
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"    WARNING: failed to fetch {url}: {e}")
        return ""

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)

    time.sleep(0.5)  # polite delay
    return html


def fetch_all_annotations(books) -> dict:
    """Scrape all 66 books and return the full annotations dict."""
    all_annotations: dict = {}

    for book in books:
        slug = _dir_to_slug(book.directory)
        print(f"  {book.name} ({book.chapters} ch)...", end=" ", flush=True)
        book_data: dict = {}

        for ch in range(1, book.chapters + 1):
            html = _fetch_chapter_html(slug, ch)
            if not html:
                continue
            chapter_data = parse_chapter_html(html)
            if chapter_data:
                book_data[str(ch)] = chapter_data

        if book_data:
            all_annotations[book.directory] = book_data
        print("done")

    return all_annotations


def main():
    import sys
    sys.path.insert(0, _SCRIPT_DIR)
    from bible_config import BOOKS

    print("Fetching Geneva annotations from StudyLight...")
    print(f"Cache: {_CACHE_DIR}")
    print(f"Output: {_OUTPUT_PATH}")
    print()

    annotations = fetch_all_annotations(BOOKS)

    os.makedirs(os.path.dirname(_OUTPUT_PATH), exist_ok=True)
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)

    total_notes = sum(
        len(anns)
        for book in annotations.values()
        for ch in book.values()
        for anns in ch.values()
    )
    print(f"\nSaved {total_notes} annotations to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests — verify they pass**

```bash
python -m pytest tests/test_annotation_fetcher.py -v
```
Expected: all 7 tests PASS.

**Step 5: Smoke-test against live site (Genesis ch. 1 only)**

```bash
cd /Users/micahcooper/geneve_1564
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from annotation_fetcher import _fetch_chapter_html, parse_chapter_html, _dir_to_slug
html = _fetch_chapter_html(_dir_to_slug('genesis'), 1)
data = parse_chapter_html(html)
print('Verses with annotations:', sorted(data.keys())[:10])
print('Genesis 1:1:', data.get('1'))
"
```
Expected: prints a list of verse numbers and the annotation for verse 1.

**Step 6: Commit**

```bash
git add scripts/annotation_fetcher.py tests/test_annotation_fetcher.py
git commit -m "feat: add annotation_fetcher to scrape Geneva Study Bible from StudyLight"
```

---

## Task 3: Fetch All Annotations

**Step 1: Run the full scrape (takes ~30 min for 1189 chapters)**

```bash
cd /Users/micahcooper/geneve_1564
python3 scripts/annotation_fetcher.py
```
Expected: prints progress, writes `data/geneva_annotations.json`.

**Step 2: Verify output**

```bash
python3 -c "
import json
with open('data/geneva_annotations.json') as f:
    d = json.load(f)
books = len(d)
total = sum(len(a) for b in d.values() for c in b.values() for a in c.values())
print(f'{books} books, {total} total annotations')
print('Sample - Genesis 1:1:', d['genesis']['1']['1'])
"
```
Expected: ~66 books, several thousand annotations.

**Step 3: Commit**

```bash
git add data/geneva_annotations.json
git commit -m "data: add scraped Geneva Bible annotations (1599 edition)"
```

---

## Task 4: latex_generator.py — Annotation Injection

**Files:**
- Modify: `scripts/latex_generator.py`
- Create: `tests/test_latex_annotations.py`

**Step 1: Write failing tests**

```python
# tests/test_latex_annotations.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from latex_generator import _build_annotation_suffix

ANNOTATIONS_V1 = [{"letter": "a", "text": "First of all, and before any creature was."}]
ANNOTATIONS_V2 = [
    {"letter": "b", "text": "An unformed lump."},
    {"letter": "c", "text": "That is, the waters."},
]


def test_no_annotations_returns_empty():
    counter = [0]
    manifest = []
    result = _build_annotation_suffix("genesis", 1, 1, [], counter, manifest)
    assert result == ""
    assert counter[0] == 0
    assert manifest == []


def test_single_annotation():
    counter = [0]
    manifest = []
    result = _build_annotation_suffix("genesis", 1, 1, ANNOTATIONS_V1, counter, manifest)
    assert r"\gva{a}" in result
    assert r"\marginnote" in result
    assert "First of all" in result
    assert counter[0] == 1
    assert manifest == [{"idx": 0, "book": "genesis", "ch": 1, "verse": 1, "letter": "a"}]


def test_two_annotations():
    counter = [0]
    manifest = []
    result = _build_annotation_suffix("genesis", 1, 2, ANNOTATIONS_V2, counter, manifest)
    assert result.count(r"\gva{") == 4  # 2 inline + 2 in marginnote
    assert result.count(r"\marginnote") == 2
    assert counter[0] == 2


def test_counter_increments_across_calls():
    counter = [5]
    manifest = []
    _build_annotation_suffix("genesis", 1, 1, ANNOTATIONS_V1, counter, manifest)
    assert counter[0] == 6
    assert manifest[0]["idx"] == 5


def test_footnote_fallback():
    counter = [0]
    manifest = []
    corrections = {0: "footnote"}
    result = _build_annotation_suffix(
        "genesis", 1, 1, ANNOTATIONS_V1, counter, manifest, corrections
    )
    assert r"\footnote" in result
    assert r"\marginnote" not in result
    assert r"\gva{a}" in result  # inline marker stays


def test_offset_correction():
    counter = [0]
    manifest = []
    corrections = {0: 24.5}
    result = _build_annotation_suffix(
        "genesis", 1, 1, ANNOTATIONS_V1, counter, manifest, corrections
    )
    assert "[24.5pt]" in result
    assert r"\marginnote[24.5pt]" in result


def test_annotation_text_latex_escaped():
    counter = [0]
    manifest = []
    anns = [{"letter": "a", "text": "Text with & ampersand and % percent."}]
    result = _build_annotation_suffix("genesis", 1, 1, anns, counter, manifest)
    assert r"\&" in result
    assert r"\%" in result
```

**Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_latex_annotations.py -v 2>&1 | head -10
```
Expected: `ImportError: cannot import name '_build_annotation_suffix'`

**Step 3: Add `_build_annotation_suffix` to latex_generator.py**

Add after the `_process_verse_text` function (after line 246):

```python
_annotations_cache: dict | None = None
_ANNOTATIONS_PATH = os.path.join(_PROJECT_ROOT, "data", "geneva_annotations.json")


def _load_annotations() -> dict:
    global _annotations_cache
    if _annotations_cache is None:
        if os.path.isfile(_ANNOTATIONS_PATH):
            with open(_ANNOTATIONS_PATH, "r", encoding="utf-8") as f:
                _annotations_cache = json.load(f)
        else:
            _annotations_cache = {}
    return _annotations_cache


def _build_annotation_suffix(
    book_dir: str,
    ch_num: int,
    verse_num: int,
    verse_annotations: list[dict],
    counter: list,
    manifest: list,
    corrections: dict | None = None,
) -> str:
    """Build the LaTeX suffix for a verse's Geneva annotations.

    Args:
        book_dir: Book directory slug (e.g. "genesis").
        ch_num: Chapter number (int).
        verse_num: Verse number (int).
        verse_annotations: List of {letter, text} dicts for this verse.
        counter: Single-element list [int] — mutable global note index.
        manifest: List to append note records to.
        corrections: Optional {manifest_idx: float | "footnote"} from overlap detector.

    Returns:
        LaTeX string to append after the verse text.
    """
    if not verse_annotations:
        return ""

    parts = []
    for ann in verse_annotations:
        idx = counter[0]
        counter[0] += 1
        manifest.append({"idx": idx, "book": book_dir, "ch": ch_num,
                          "verse": verse_num, "letter": ann["letter"]})

        letter = ann["letter"]
        text = _escape_latex(_convert_smart_quotes(ann["text"]))
        inline = f"\\gva{{{letter}}}"
        note_content = f"\\gva{{{letter}}}\\,{text}"

        correction = corrections.get(idx, 0) if corrections else 0
        if correction == "footnote":
            parts.append(f"{inline}\\footnote{{{note_content}}}")
        elif correction:
            parts.append(f"{inline}\\marginnote[{correction:.1f}pt]{{{note_content}}}")
        else:
            parts.append(f"{inline}\\marginnote{{{note_content}}}")

    return "".join(parts)
```

**Step 4: Run tests — verify they pass**

```bash
python -m pytest tests/test_latex_annotations.py -v
```
Expected: all 7 tests PASS.

**Step 5: Update `generate_book_tex` signature and wire in annotations**

In `generate_book_tex` (starting at line 249), update the signature:

```python
def generate_book_tex(
    book: BookInfo,
    chapters_data: dict[int, list[dict]],
    plan_endpoints: dict | None = None,
    annotations: dict | None = None,
    corrections: dict | None = None,
    note_manifest: list | None = None,
) -> str:
```

At the top of the function body, after `lines = []`, add:
```python
    # Load annotations for this book if not provided explicitly
    if annotations is None:
        all_annotations = _load_annotations()
        annotations = all_annotations.get(book.directory, {})

    # Thread a mutable counter and manifest through note generation
    _counter = [0] if note_manifest is None else None
    _local_manifest: list = [] if note_manifest is None else note_manifest
    note_counter = _counter if _counter is not None else [
        _local_manifest[-1]["idx"] + 1 if _local_manifest else 0
    ]
```

Wait — the counter must be global across all books (so manifest indices match PDF order). The cleanest approach: pass `note_manifest` as a shared list from the caller. When `note_manifest` is passed, the counter starts at `len(note_manifest)`.

Revised setup block at the top of `generate_book_tex`:
```python
    if annotations is None:
        all_annotations = _load_annotations()
        annotations = all_annotations.get(book.directory, {})
    else:
        annotations = annotations.get(book.directory, annotations)

    _manifest = note_manifest if note_manifest is not None else []
    _counter = [len(_manifest)]
```

In the verse emission section, after `text = _process_verse_text(raw_html)`, add:
```python
    ch_annotations = annotations.get(str(ch_num), {})
    verse_anns = ch_annotations.get(str(verse_num), [])
    ann_suffix = _build_annotation_suffix(
        book.directory, ch_num, verse_num, verse_anns,
        _counter, _manifest, corrections
    )
```

Then append `ann_suffix` to the verse text in the three emission paths (verse 1 lettrine, new_para, and normal verse). For example:

Line 325: `lines.append(f"\\ch{{{ch_num}}} \\allowchapbreak...{lettrine_text}\\everypar{{}}")`
Becomes: `lines.append(f"\\ch{{{ch_num}}} \\allowchapbreak...{lettrine_text}{ann_suffix}\\everypar{{}}")`

Line 334: `lines.append(f"\\\\\\indent{mark}\\vs{{{verse_num}}} {text}")`
Becomes: `lines.append(f"\\\\\\indent{mark}\\vs{{{verse_num}}} {text}{ann_suffix}")`

Line 339: `lines.append(f"{mark}\\vs{{{verse_num}}} {text}")`
Becomes: `lines.append(f"{mark}\\vs{{{verse_num}}} {text}{ann_suffix}")`

Line 341: `lines.append(f"{mark}\\vs{{{verse_num}}} {text}")`
Becomes: `lines.append(f"{mark}\\vs{{{verse_num}}} {text}{ann_suffix}")`

**Step 6: Write note manifest to file in generate_bible.py**

In `generate_bible.py`, create a shared manifest list before the book loop, pass it to `generate_book_tex`, and write it after the loop:

After `plan_endpoints = build_plan_endpoints(scheduled)` (around line 102), add:
```python
    note_manifest: list = []
```

Change `generate_book_tex` call (line 120) to:
```python
        tex_content = generate_book_tex(
            book, chapters_data,
            plan_endpoints=plan_endpoints,
            note_manifest=note_manifest,
        )
```

After the book loop (after the `print("Done!")` or before it), add:
```python
    manifest_path = os.path.join(_PROJECT_ROOT, "data", "note_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(note_manifest, f)
    print(f"  note_manifest.json written ({len(note_manifest)} notes)")
```

**Step 7: Smoke-test annotation injection for Genesis**

```bash
cd /Users/micahcooper/geneve_1564
python3 scripts/generate_bible.py --books genesis
grep -c "\\\\gva" livres/genesis/genesis.tex
```
Expected: non-zero count of `\gva` occurrences.

```bash
grep "\\\\gva" livres/genesis/genesis.tex | head -3
```
Expected: lines like `...text\gva{a}\marginnote{\gva{a}\,...`

**Step 8: Compile genesis-only test**

Temporarily modify `net_bible.tex` to only include genesis, compile, check for errors:
```bash
OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=batchmode net_bible.tex 2>&1 | grep -E "^!" | head -10
```
Expected: no lines starting with `!` (no LaTeX errors). Revert the temporary change.

**Step 9: Commit**

```bash
git add scripts/latex_generator.py scripts/generate_bible.py tests/test_latex_annotations.py
git commit -m "feat: inject Geneva annotation markers and marginnotes into verse text"
```

---

## Task 5: overlap_detector.py

**Files:**
- Create: `scripts/overlap_detector.py`
- Create: `tests/test_overlap_detector.py`

**Step 1: Write failing tests**

```python
# tests/test_overlap_detector.py
from overlap_detector import detect_overlaps_from_rects, _identify_margin_notes

PAGE_WIDTH = 507.0
PAGE_HEIGHT = 677.0
MARGIN_X = 435.0


def test_no_overlap():
    # Two notes with 5pt gap between them
    rects = [(436, 100, 500, 120), (436, 125, 500, 145)]
    corrections = detect_overlaps_from_rects(rects, gap=2.0, page_height=PAGE_HEIGHT)
    assert corrections == {}


def test_single_overlap():
    # Note 0 ends at y=120, note 1 starts at y=115 — overlap of 5pt
    rects = [(436, 100, 500, 120), (436, 115, 500, 135)]
    corrections = detect_overlaps_from_rects(rects, gap=2.0, page_height=PAGE_HEIGHT)
    # Note 1 should be pushed down by (120 + 2) - 115 = 7pt
    assert 1 in corrections
    assert abs(corrections[1] - 7.0) < 0.1


def test_cascade_overlap():
    # Three notes: 0 and 1 overlap, pushing 1 causes 1 and 2 to overlap
    rects = [(436, 100, 500, 120), (436, 115, 500, 135), (436, 132, 500, 152)]
    corrections = detect_overlaps_from_rects(rects, gap=2.0, page_height=PAGE_HEIGHT)
    # Note 1 pushed to y=122 (bottom at 142), note 2 pushed to y=144 (bottom at 164)
    assert 1 in corrections
    assert 2 in corrections
    assert corrections[2] > corrections[1]


def test_footnote_fallback_when_off_page():
    # Note pushed so far it would fall off bottom
    rects = [(436, 600, 500, 620), (436, 610, 500, 630)]
    corrections = detect_overlaps_from_rects(
        rects, gap=2.0, page_height=PAGE_HEIGHT, bottom_margin=36.0
    )
    # 620 + 2 = 622, note 1 pushed to start at 622, end at 642
    # 642 > 677 - 36 = 641 → footnote
    assert corrections[1] == "footnote"


def test_identify_margin_notes_filters_by_x():
    blocks = [
        {"bbox": (50, 100, 400, 110), "text": "main text"},
        {"bbox": (440, 100, 500, 110), "text": "(a) margin note"},
        {"bbox": (440, 200, 500, 210), "text": "(b) another note"},
    ]
    notes = _identify_margin_notes(blocks, margin_x=435.0)
    assert len(notes) == 2
    assert notes[0]["text"] == "(a) margin note"
```

**Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_overlap_detector.py -v 2>&1 | head -10
```
Expected: `ImportError: No module named 'overlap_detector'`

**Step 3: Implement overlap_detector.py**

```python
# scripts/overlap_detector.py
"""Detect overlapping margin notes in a compiled PDF using PyMuPDF."""

import json
import os

import fitz  # PyMuPDF

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

MARGIN_X = 435.0      # x-coordinate beyond which text is in the outer margin
GAP = 2.0             # minimum gap in points between adjacent margin notes
BOTTOM_MARGIN = 36.0  # points from page bottom — notes pushed past here → footnote


def _identify_margin_notes(blocks: list, margin_x: float = MARGIN_X) -> list:
    """Filter text blocks to those in the outer margin zone."""
    return [b for b in blocks if b["bbox"][0] > margin_x]


def detect_overlaps_from_rects(
    rects: list[tuple],
    gap: float = GAP,
    page_height: float = 677.0,
    bottom_margin: float = BOTTOM_MARGIN,
) -> dict:
    """Detect overlapping bounding boxes and compute push-down corrections.

    Args:
        rects: List of (x0, y0, x1, y1) tuples, already sorted by y0.
        gap: Minimum gap in points between notes.
        page_height: Page height in points.
        bottom_margin: Notes pushed past (page_height - bottom_margin) become footnotes.

    Returns:
        {note_index: offset_pt} or {note_index: "footnote"} for notes needing correction.
        Only indices needing correction are present.
    """
    corrections = {}
    adjusted = list(rects)  # mutable copy for cascade tracking

    for i in range(len(adjusted) - 1):
        x0_i, y0_i, x1_i, y1_i = adjusted[i]
        x0_j, y0_j, x1_j, y1_j = adjusted[i + 1]

        if y1_i + gap > y0_j:
            push = (y1_i + gap) - y0_j
            new_y0 = y0_j + push
            new_y1 = y1_j + push
            adjusted[i + 1] = (x0_j, new_y0, x1_j, new_y1)

            # Accumulate total push for this note
            total_push = corrections.get(i + 1, 0)
            if total_push == "footnote":
                continue
            total_push = total_push + push if isinstance(total_push, float) else push

            if new_y1 > page_height - bottom_margin:
                corrections[i + 1] = "footnote"
            else:
                corrections[i + 1] = total_push

    return corrections


def detect(pdf_path: str, manifest_path: str) -> dict:
    """Detect overlapping margin notes in a compiled PDF.

    Matches margin notes in the PDF (by sequence) to manifest entries,
    returns corrections keyed by manifest idx.

    Args:
        pdf_path: Path to the compiled PDF.
        manifest_path: Path to note_manifest.json.

    Returns:
        {manifest_idx: offset_pt | "footnote"}
    """
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    doc = fitz.open(pdf_path)
    all_corrections: dict = {}

    # Collect all margin note rects across the document in order
    # (page 0 first, then y-sorted within each page)
    all_page_notes: list[list] = []

    for page in doc:
        page_width = page.rect.width
        page_height = page.rect.height
        margin_x = page_width * 0.86  # ~86% across = start of outer margin

        raw_blocks = page.get_text("dict")["blocks"]
        text_blocks = [
            {"bbox": b["bbox"], "text": " ".join(
                span["text"]
                for line in b.get("lines", [])
                for span in line.get("spans", [])
            )}
            for b in raw_blocks if b["type"] == 0  # type 0 = text
        ]
        margin_blocks = _identify_margin_notes(text_blocks, margin_x=margin_x)
        margin_blocks.sort(key=lambda b: b["bbox"][1])  # sort by y0

        rects = [b["bbox"] for b in margin_blocks]
        page_corrections = detect_overlaps_from_rects(
            rects, gap=GAP, page_height=page_height, bottom_margin=BOTTOM_MARGIN
        )

        all_page_notes.append((rects, page_corrections, page_height))

    doc.close()

    # Match margin notes to manifest by global sequence
    global_note_idx = 0
    for rects, page_corrections, page_height in all_page_notes:
        for local_i, _rect in enumerate(rects):
            if global_note_idx >= len(manifest):
                break
            if local_i in page_corrections:
                manifest_idx = manifest[global_note_idx]["idx"]
                all_corrections[manifest_idx] = page_corrections[local_i]
            global_note_idx += 1

    return all_corrections
```

**Step 4: Run tests — verify they pass**

```bash
python -m pytest tests/test_overlap_detector.py -v
```
Expected: all 5 tests PASS.

**Step 5: Commit**

```bash
git add scripts/overlap_detector.py tests/test_overlap_detector.py
git commit -m "feat: add PyMuPDF overlap detector for margin notes"
```

---

## Task 6: build_annotated.py — Compile Loop

**Files:**
- Create: `scripts/build_annotated.py`

**Step 1: Implement build_annotated.py**

```python
#!/usr/bin/env python3
# scripts/build_annotated.py
"""Compile net_bible.tex with iterative overlap correction for margin notes.

Usage:
    python3 scripts/build_annotated.py [--books genesis] [--max-iter 3]
"""

import argparse
import json
import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)

from bible_config import BOOKS, get_book_by_name
from bible_fetcher import fetch_book
from latex_generator import generate_book_tex, generate_testament_tex, generate_color_index_tex
from overlap_detector import detect

_MANIFEST_PATH = os.path.join(_PROJECT_ROOT, "data", "note_manifest.json")
_PDF_PATH = os.path.join(_PROJECT_ROOT, "net_bible.pdf")
_LUALATEX = [
    "lualatex", "-shell-escape", "-interaction=batchmode", "net_bible.tex"
]
_ENV = {**os.environ, "OSFONTDIR": "fonts", "TEXINPUTS": "microtype:"}


def _compile():
    print("  Compiling...", end=" ", flush=True)
    result = subprocess.run(
        _LUALATEX, cwd=_PROJECT_ROOT, env=_ENV,
        capture_output=True, text=True
    )
    # Run twice for cross-references
    if result.returncode == 0:
        result = subprocess.run(
            _LUALATEX, cwd=_PROJECT_ROOT, env=_ENV,
            capture_output=True, text=True
        )
    if result.returncode != 0:
        print("FAILED")
        print(result.stdout[-2000:])
        sys.exit(1)
    print("ok")


def _generate(books_to_generate, output_dir, cache_dir, corrections=None):
    note_manifest: list = []
    for book in books_to_generate:
        chapters_data = fetch_book(book.abbreviation, book.chapters, cache_dir)
        tex_content = generate_book_tex(
            book, chapters_data,
            note_manifest=note_manifest,
            corrections=corrections,
        )
        book_dir = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir, exist_ok=True)
        with open(os.path.join(book_dir, f"{book.directory}.tex"), "w") as f:
            f.write(tex_content)

    with open(_MANIFEST_PATH, "w") as f:
        json.dump(note_manifest, f)
    print(f"  {len(note_manifest)} annotation notes in manifest")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--books", nargs="+")
    parser.add_argument("--max-iter", type=int, default=3)
    parser.add_argument(
        "--output-dir", default=os.path.join(_PROJECT_ROOT, "livres")
    )
    parser.add_argument(
        "--cache-dir",
        default=os.path.join(_PROJECT_ROOT, "data", "net_bible_cache")
    )
    args = parser.parse_args()

    if args.books:
        books = []
        for name in args.books:
            b = get_book_by_name(name)
            if b is None:
                print(f"Unknown book: {name}", file=sys.stderr)
                sys.exit(1)
            books.append(b)
    else:
        books = BOOKS

    corrections: dict = {}

    for iteration in range(1, args.max_iter + 1):
        print(f"\n=== Iteration {iteration}/{args.max_iter} ===")
        print("Generating .tex files...")
        _generate(books, args.output_dir, args.cache_dir, corrections or None)

        _compile()

        print("Detecting overlaps...")
        new_corrections = detect(_PDF_PATH, _MANIFEST_PATH)

        if not new_corrections:
            print(f"No overlaps — done after {iteration} iteration(s).")
            break

        n_offsets = sum(1 for v in new_corrections.values() if v != "footnote")
        n_footnotes = sum(1 for v in new_corrections.values() if v == "footnote")
        print(f"  {n_offsets} offset corrections, {n_footnotes} footnote demotions")

        corrections.update(new_corrections)

        if iteration == args.max_iter:
            print(f"Reached max iterations ({args.max_iter}). Applying final corrections.")
            print("Regenerating with final corrections...")
            _generate(books, args.output_dir, args.cache_dir, corrections)
            _compile()

    print("\nDone.")


if __name__ == "__main__":
    main()
```

**Step 2: Smoke-test with a single book**

```bash
cd /Users/micahcooper/geneve_1564
python3 scripts/build_annotated.py --books genesis --max-iter 2
```
Expected: runs 1–2 iterations, exits cleanly, `net_bible.pdf` updated.

**Step 3: Inspect the output PDF**

Open `net_bible.pdf` and navigate to Genesis. Verify:
- Superscript letters `a`, `b`, `c` appear after verse text
- Matching notes appear in the right margin
- No visible overlap between adjacent notes

**Step 4: Commit**

```bash
git add scripts/build_annotated.py
git commit -m "feat: add build_annotated.py compile-detect-correct loop"
```

---

## Task 7: Makefile Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add targets**

After the `generate-esv:` target (line 28), add:

```makefile
fetch-annotations:
	python3 scripts/annotation_fetcher.py

build-annotated:
	python3 scripts/build_annotated.py

build-annotated-book:
	python3 scripts/build_annotated.py --books $(BOOK)
```

**Step 2: Verify**

```bash
make -n fetch-annotations
make -n build-annotated
```
Expected: prints the commands without executing them.

**Step 3: Commit**

```bash
git add Makefile
git commit -m "feat: add fetch-annotations and build-annotated Makefile targets"
```

---

## Task 8: Full Build

**Step 1: Run full annotated build**

```bash
cd /Users/micahcooper/geneve_1564
python3 scripts/build_annotated.py --max-iter 3 2>&1 | tee build_annotated.log
```
Expected: 1–3 iterations, final PDF written.

**Step 2: Inspect PDF**

Open `net_bible.pdf`. Spot-check several books:
- Genesis (dense annotations)
- Psalms (poetry)
- Romans (NT)

Verify: margin notes visible, no visible overlap, inline markers present.

**Step 3: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: all tests pass.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Geneva annotations implementation"
```

---

## Summary of New Files

| File | Purpose |
|------|---------|
| `scripts/annotation_fetcher.py` | Scrape StudyLight, cache HTML, output JSON |
| `scripts/overlap_detector.py` | PyMuPDF-based overlap detection |
| `scripts/build_annotated.py` | Compile → detect → correct → recompile loop |
| `tests/conftest.py` | Pytest path setup |
| `tests/test_annotation_fetcher.py` | Tests for HTML parsing + URL slugs |
| `tests/test_latex_annotations.py` | Tests for annotation LaTeX emission |
| `tests/test_overlap_detector.py` | Tests for overlap algorithm |
| `data/geneva_annotations.json` | Scraped annotation data |
| `data/annotations_cache/` | Per-chapter HTML cache |
| `data/note_manifest.json` | Generated per-run; maps note indices to keys |

## Summary of Modified Files

| File | Change |
|------|--------|
| `net_bible.tex` | Add `\usepackage{marginnote}`, `\newcommand{\gva}` |
| `scripts/latex_generator.py` | Add `_build_annotation_suffix`, update `generate_book_tex` |
| `scripts/generate_bible.py` | Pass `note_manifest` to `generate_book_tex`, write manifest |
| `scripts/requirements.txt` | Add `pymupdf`, `beautifulsoup4`, `lxml` |
| `Makefile` | Add `fetch-annotations`, `build-annotated` targets |
