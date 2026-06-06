# NET Red-Letter Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the NET edition's per-verse red-letter heuristic with a chapter-level state machine so Words of Christ stay red through multi-verse quotations and arbitrarily nested quotes.

**Architecture:** A builder parses WEB USFM `\wj` markers into a per-verse descriptor (`{opens: [bool…], starts_in_jesus: bool}`). At render time, a state machine threads quote-nesting depth and "in Jesus" status across a chapter's verses: WEB decides *which* quotes are Jesus; NET's own quotation marks decide *where* they are; double-quote depth keeps nested quotes red. The proven ESV pattern (per-verse `\redletteron … \redletteroff`, black verse numbers) is reproduced.

**Tech Stack:** Python 3.13, stdlib only (`re`, `json`, `glob`). Tests are plain `assert` scripts run with `python3` (matches existing `tests/test_latex_escaping.py`).

**Design doc:** `docs/plans/2026-06-05-net-red-letter-design.md`

---

## File Structure

- **Modify** `scripts/build_red_letter_data.py` — emit v2 per-verse descriptors instead of a verse-number list. New pure function `parse_verse_descriptor(raw)` + `_clean_web_verse(raw)`.
- **Modify** `scripts/latex_generator.py` — replace `_is_red_letter` / `_apply_red_letter_quotes` with `_get_red_letter_desc`, a `_RLState` class, and `_render_red_letter`; thread state through the verse loop in `generate_book_tex`.
- **Create** `tests/test_red_letter.py` — unit tests for the builder parser and the renderer state machine.
- **Regenerate** `data/red_letter_verses.json` (gitignored; `git add -f` if committing).

---

## Task 1: WEB USFM cleaner

Strips USFM markup from a raw verse string, leaving plain text with `\x01`/`\x02` sentinels marking the start/end of `\wj` (words-of-Jesus) spans.

**Files:**
- Modify: `scripts/build_red_letter_data.py`
- Test: `tests/test_red_letter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_red_letter.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_red_letter_data as brd

_failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}: {detail}")
        _failures.append(name)


print("build_red_letter_data._clean_web_verse")

# Real WEB Matthew 4:4 shape: \wj span, \+w word markup, nested quotes, \x crossref.
raw_44 = (
    r'\w But|strong="G1161"\w* \w he|strong="G1161"\w* \w answered|strong="G3004"\w*, '
    '\\wj “\\+w It|strong="G1161"\\+w* \\+w is|strong="G3588"\\+w* '
    '\\+w written|strong="G1125"\\+w*, ‘\\+w Man|strong="G3956"\\+w* shall not live'
    '’”\\wj*\\x + \\xo 4:4 \\xt Deuteronomy 8:3\\x*'
)
cleaned = brd._clean_web_verse(raw_44)
check("strips \\w markup", "But he answered" in cleaned, cleaned)
check("keeps wj open sentinel", "\x01" in cleaned, repr(cleaned))
check("keeps wj close sentinel", "\x02" in cleaned, repr(cleaned))
check("drops crossref text", "Deuteronomy" not in cleaned, repr(cleaned))
check("keeps quote chars", "“" in cleaned and "‘" in cleaned, repr(cleaned))

# Footnote text (with its own quotes) must be removed entirely.
raw_fn = r'foo \f + \ft means “Anointed”\f* bar'
check("drops footnote text",
      brd._clean_web_verse(raw_fn).replace("\x01", "").replace("\x02", "").split()
      == ["foo", "bar"],
      repr(brd._clean_web_verse(raw_fn)))

if _failures:
    print(f"\n{len(_failures)} FAILED: {_failures}")
    sys.exit(1)
print("\nAll tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_red_letter.py`
Expected: FAIL with `AttributeError: module 'build_red_letter_data' has no attribute '_clean_web_verse'`

- [ ] **Step 3: Add `_clean_web_verse` to `scripts/build_red_letter_data.py`**

Add after the imports / constants block (before `parse_usfm_for_wj`):

```python
def _clean_web_verse(raw: str) -> str:
    r"""Strip USFM markup from a verse, marking \wj spans with sentinels.

    Returns plain text where '\x01' marks a words-of-Jesus span opening and
    '\x02' marks its close. Footnotes (\f..\f*) and cross-references
    (\x..\x*) are removed entirely (they contain quotes we must not count).
    """
    t = raw
    # Remove footnotes and cross-references (may contain quotes/markers).
    t = re.sub(r"\\f .*?\\f\*", "", t)
    t = re.sub(r"\\x .*?\\x\*", "", t)
    # Mark words-of-Jesus spans with sentinels (\wj* before \wj to be safe).
    t = t.replace(r"\wj*", "\x02")
    t = re.sub(r"\\wj\b", "\x01", t)
    # Unwrap word markup: \+w word|strong=..\+w*  and  \w word|..\w*  -> word
    t = re.sub(r"\\\+w ([^\\|]*)(?:\|[^\\]*?)?\\\+w\*", r"\1", t)
    t = re.sub(r"\\w ([^\\|]*)(?:\|[^\\]*?)?\\w\*", r"\1", t)
    # Drop any remaining USFM markers (\q1, \q2, \p, \m, \b, \nb, ...).
    t = re.sub(r"\\[a-z]+\d*\*?", " ", t)
    return t
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_red_letter.py`
Expected: PASS (`All tests passed.`)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_red_letter_data.py tests/test_red_letter.py
git commit -m "feat(red-letter): WEB USFM verse cleaner with \\wj sentinels"
```

---

## Task 2: Verse descriptor parser

Turns a cleaned verse into `{opens: [bool…], starts_in_jesus: bool}` or `None` when the verse has no Words of Christ.

**Files:**
- Modify: `scripts/build_red_letter_data.py`
- Test: `tests/test_red_letter.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_red_letter.py` (before the `if _failures:` block):

```python
print("build_red_letter_data.parse_verse_descriptor")

OPEN, CLOSE, SOPEN, SCLOSE = "“", "”", "‘", "’"

def wj(s):  # wrap in a words-of-Jesus span
    return r"\wj " + s + r"\wj*"

# Leading frame: narrator, then Jesus opens a quote.
d = brd.parse_verse_descriptor("He answered, " + wj(OPEN + "It is written." + CLOSE))
check("leading frame opens=[True]", d == {"opens": [True], "starts_in_jesus": False}, d)

# Continuation verse: \wj words, no quote mark.
d = brd.parse_verse_descriptor(wj("Blessed are those who mourn,"))
check("continuation starts_in_jesus", d == {"opens": [], "starts_in_jesus": True}, d)

# Mixed speaker: crowd quote (not wj) then Jesus quote (wj).
d = brd.parse_verse_descriptor(
    "they said, " + OPEN + "We don't know." + CLOSE + " he said, "
    + wj(OPEN + "Neither will I." + CLOSE))
check("mixed speaker opens=[False,True]",
      d == {"opens": [False, True], "starts_in_jesus": False}, d)

# Non-Jesus quote only -> None.
d = brd.parse_verse_descriptor("they said, " + OPEN + "We don't know." + CLOSE)
check("non-jesus -> None", d is None, d)

# Nested Scripture quote inside Jesus' words: one top-level open, still Jesus.
d = brd.parse_verse_descriptor(
    "he answered, " + wj(OPEN + "It is written, " + SOPEN + "Man shall not live"
                         + SCLOSE + CLOSE))
check("nested single stays one top-level open",
      d == {"opens": [True], "starts_in_jesus": False}, d)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_red_letter.py`
Expected: FAIL with `AttributeError: ... 'parse_verse_descriptor'`

- [ ] **Step 3: Add `parse_verse_descriptor` to `scripts/build_red_letter_data.py`**

Add directly after `_clean_web_verse`:

```python
def parse_verse_descriptor(raw: str):
    r"""Return {"opens": [bool...], "starts_in_jesus": bool} or None.

    opens: one flag per TOP-LEVEL double-quote open in the verse, in order;
           True if that quote begins inside a \wj (Jesus) span.
    starts_in_jesus: the verse's first content begins inside a \wj span with
           no opening double quote (a continuation verse).
    Returns None if the verse contains no Words of Christ.
    """
    t = _clean_web_verse(raw)
    in_wj = False
    depth = 0
    opens: list[bool] = []
    starts = False
    seen = False
    jesus = False
    for ch in t:
        if ch == "\x01":
            in_wj = True
            continue
        if ch == "\x02":
            in_wj = False
            continue
        if ch == "“":  # open double
            if depth == 0:
                opens.append(in_wj)
            if in_wj:
                jesus = True
            depth += 1
            seen = True
            continue
        if ch == "”":  # close double
            depth = max(0, depth - 1)
            seen = True
            continue
        if ch.isspace():
            continue
        if not seen:
            seen = True
            if in_wj and depth == 0:
                starts = True
        if in_wj:
            jesus = True
    if not jesus:
        return None
    return {"opens": opens, "starts_in_jesus": starts}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_red_letter.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_red_letter_data.py tests/test_red_letter.py
git commit -m "feat(red-letter): parse WEB verse into red-letter descriptor"
```

---

## Task 3: Rewire the builder to emit v2 descriptors

Replace `parse_usfm_for_wj` + `main`'s output so the JSON is
`{"_format": 2, "<book>": {"<chapter>": {"<verse>": descriptor}}}`.

**Files:**
- Modify: `scripts/build_red_letter_data.py`

- [ ] **Step 1: Replace `parse_usfm_for_wj`**

Replace the whole `parse_usfm_for_wj` function (currently lines ~33-64) with:

```python
def parse_usfm_for_descriptors(filepath: str) -> dict[str, dict[str, dict]]:
    """Return {chapter_str: {verse_str: descriptor}} for one USFM file."""
    result: dict[str, dict[str, dict]] = {}
    current_chapter: int | None = None
    current_verse: int | None = None
    verse_parts: list[str] = []

    _C = re.compile(r"\\c\s+(\d+)")
    _V = re.compile(r"\\v\s+(\d+)\s*(.*)")

    def flush():
        if current_chapter is not None and current_verse is not None:
            desc = parse_verse_descriptor(" ".join(verse_parts))
            if desc is not None:
                ch = str(current_chapter)
                result.setdefault(ch, {})[str(current_verse)] = desc

    with open(filepath, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            mc = _C.match(line)
            mv = _V.match(line)
            if mc:
                flush()
                verse_parts = []
                current_verse = None
                current_chapter = int(mc.group(1))
            elif mv:
                flush()
                current_verse = int(mv.group(1))
                verse_parts = [mv.group(2)]
            elif current_verse is not None:
                verse_parts.append(line)

    flush()
    return result
```

- [ ] **Step 2: Update `main` to use the new parser and format**

In `main`, change the call and the per-book summary, and add the `_format` key:

```python
def main() -> None:
    all_data: dict[str, object] = {"_format": 2}

    for filepath in sorted(glob.glob(os.path.join(_USFM_DIR, "*.usfm"))):
        filename = os.path.basename(filepath)
        m = re.search(r"\d+-([A-Z1-9]{3})", filename)
        if not m:
            continue
        code = m.group(1)
        if code not in _CODE_TO_DIR:
            continue

        book_dir = _CODE_TO_DIR[code]
        data = parse_usfm_for_descriptors(filepath)
        if data:
            all_data[book_dir] = data
            total = sum(len(v) for v in data.values())
            print(f"  {book_dir}: {total} red-letter verses across {len(data)} chapters")

    with open(_OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(all_data, fh, indent=2)

    print(f"\nWrote {_OUTPUT_PATH}")
```

- [ ] **Step 3: Run the builder and sanity-check output**

Run:
```bash
python3 scripts/build_red_letter_data.py
python3 -c "import json; d=json.load(open('data/red_letter_verses.json')); \
print('format', d['_format']); \
print('Mt5:3', d['matthew']['5']['3']); \
print('Mt5:4', d['matthew']['5']['4'])"
```
Expected: `format 2`; `Mt5:3 {'opens': [True], 'starts_in_jesus': False}`; `Mt5:4 {'opens': [], 'starts_in_jesus': True}`

- [ ] **Step 4: Commit**

```bash
git add scripts/build_red_letter_data.py
git commit -m "feat(red-letter): builder emits v2 per-verse descriptors"
```

---

## Task 4: Renderer state machine

Pure-string renderer that inserts `\redletteron`/`\redletteroff` into one verse's TeX text, threading state across a chapter.

**Files:**
- Modify: `scripts/latex_generator.py`
- Test: `tests/test_red_letter.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_red_letter.py` (before the `if _failures:` block):

```python
print("latex_generator._render_red_letter")
import latex_generator as lg

# Render a chapter of verses given (text, descriptor) pairs; return list of
# rendered strings sharing one state.
def render_chapter(verses):
    st = lg._RLState()
    return [lg._render_red_letter(t, d, st) for (t, d) in verses]

D = lambda opens, starts: {"opens": opens, "starts_in_jesus": starts}

# Sermon continuation: v3 opens, v4 continues (NET closes each beatitude).
out = render_chapter([
    ("``Blessed are the poor in spirit.''", D([True], False)),
    ("``Blessed are those who mourn.''", D([], True)),
])
check("v3 leading wraps quote",
      out[0] == "\\redletteron ``Blessed are the poor in spirit.''\\redletteroff ", out[0])
check("v4 continuation is red",
      out[1].startswith("\\redletteron ") and out[1].rstrip().endswith("\\redletteroff"),
      out[1])

# Plain narration after Jesus stops: descriptor None closes red, stays off.
st = lg._RLState()
a = lg._render_red_letter("``I am he.''", D([True], False), st)
b = lg._render_red_letter("Then they left.", None, st)
check("narration after jesus is black", "redletter" not in b, b)
check("narration does not reopen", b == "Then they left.", b)

# Mixed speaker: crowd quote black, Jesus quote red.
st = lg._RLState()
m = lg._render_red_letter(
    "they said, ``We don't know.'' he said, ``Neither.''",
    D([False, True], False), st)
check("mixed: crowd quote not preceded by redletteron",
      m.index("``We") < m.find("\\redletteron") if "\\redletteron" in m else False, m)
check("mixed: jesus quote turns red",
      "\\redletteron ``Neither.''\\redletteroff" in m, m)

# 3rd-level nesting: inner double must NOT end the red early.
st = lg._RLState()
n = lg._render_red_letter(
    "``It is `the stone the builders ``rejected'' became' great.''",
    D([True], False), st)
check("nesting: exactly one redletteron", n.count("\\redletteron") == 1, n)
check("nesting: exactly one redletteroff", n.count("\\redletteroff") == 1, n)
check("nesting: red closes at the very end",
      n.rstrip().endswith("\\redletteroff"), n)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_red_letter.py`
Expected: FAIL with `AttributeError: ... '_RLState'`

- [ ] **Step 3: Add `_RLState` and `_render_red_letter` to `scripts/latex_generator.py`**

Replace the existing `_apply_red_letter_quotes` function (currently lines ~37-63) with:

```python
class _RLState:
    """Red-letter state carried across the verses of one chapter."""

    def __init__(self) -> None:
        self.in_jesus = False
        self.depth = 0           # double-quote nesting depth
        self.open_depth = None   # depth at which the active Jesus quote opened


def _render_red_letter(text: str, desc, state: "_RLState") -> str:
    r"""Insert \redletteron/\redletteroff into one verse's TeX text.

    desc is {"opens": [bool...], "starts_in_jesus": bool} or None (no Words of
    Christ in this verse). Mutates `state`. Red turns off only when double-quote
    depth returns to the level where Jesus' quote opened, so nested quotes
    (single, or 3rd-level double) stay red. Each verse's trailing \redletteroff
    keeps the next verse number black; carried `in_jesus` reopens it.
    """
    OPEN, CLOSE = "``", "''"
    out: list[str] = []

    if desc is None:
        if state.in_jesus:
            out.append("\\redletteroff ")
            state.in_jesus = False
            state.open_depth = None
        out.append(text)
        return "".join(out)

    if state.in_jesus or desc.get("starts_in_jesus"):
        if not state.in_jesus:
            state.in_jesus = True
            state.open_depth = state.depth
        out.append("\\redletteron ")

    opens = desc.get("opens", [])
    k = 0
    i = 0
    n = len(text)
    while i < n:
        two = text[i:i + 2]
        if two == OPEN:
            if state.depth == 0:  # top-level open
                if not state.in_jesus:
                    is_j = opens[k] if k < len(opens) else False
                    if is_j:
                        out.append("\\redletteron ")
                        state.in_jesus = True
                        state.open_depth = state.depth
                k += 1
            state.depth += 1
            out.append(OPEN)
            i += 2
            continue
        if two == CLOSE:
            state.depth = max(0, state.depth - 1)
            out.append(CLOSE)
            i += 2
            if state.in_jesus and state.depth == state.open_depth:
                out.append("\\redletteroff ")
                state.in_jesus = False
                state.open_depth = None
            continue
        out.append(text[i])
        i += 1

    if state.in_jesus:
        out.append("\\redletteroff ")
    return "".join(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_red_letter.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/latex_generator.py tests/test_red_letter.py
git commit -m "feat(red-letter): chapter-level renderer state machine"
```

---

## Task 5: Descriptor lookup + loader (v2-aware)

Replace `_is_red_letter` with `_get_red_letter_desc`.

**Files:**
- Modify: `scripts/latex_generator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_red_letter.py` (before the `if _failures:` block):

```python
print("latex_generator._get_red_letter_desc")
# Inject a fake v2 dataset and confirm lookup returns descriptors / None.
lg._red_letter_verses = {
    "_format": 2,
    "john": {"3": {"16": {"opens": [True], "starts_in_jesus": False}}},
}
check("desc lookup hit",
      lg._get_red_letter_desc("john", 3, 16) == {"opens": [True], "starts_in_jesus": False},
      lg._get_red_letter_desc("john", 3, 16))
check("desc lookup miss", lg._get_red_letter_desc("john", 3, 17) is None, "miss")
check("desc lookup unknown book", lg._get_red_letter_desc("genesis", 1, 1) is None, "book")
lg._red_letter_verses = None  # reset cache
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_red_letter.py`
Expected: FAIL with `AttributeError: ... '_get_red_letter_desc'`

- [ ] **Step 3: Replace `_is_red_letter` in `scripts/latex_generator.py`**

Replace the `_is_red_letter` function (currently lines ~31-34) with:

```python
def _get_red_letter_desc(book_dir: str, chapter: int, verse: int):
    """Return the red-letter descriptor for a verse, or None.

    Descriptor: {"opens": [bool...], "starts_in_jesus": bool}. Returns None for
    verses with no Words of Christ (or legacy/missing data).
    """
    data = _load_red_letter_verses()
    chapters = data.get(book_dir)
    if not isinstance(chapters, dict):
        return None
    verses = chapters.get(str(chapter))
    if not isinstance(verses, dict):  # legacy list format -> no descriptors
        return None
    return verses.get(str(verse))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_red_letter.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/latex_generator.py tests/test_red_letter.py
git commit -m "feat(red-letter): v2-aware descriptor lookup"
```

---

## Task 6: Integrate into the verse loop

Thread one `_RLState` per chapter through both verse render paths in
`generate_book_tex`.

**Files:**
- Modify: `scripts/latex_generator.py` (the verse loop, currently ~358-410)

- [ ] **Step 1: Initialize state once per chapter**

In `generate_book_tex`, immediately after `lettrine_char_budget = 0`
(currently line ~369, just before `for verse in verses:`), add:

```python
        rl_state = _RLState()
```

- [ ] **Step 2: Replace the verse-1 (lettrine) red-letter call**

Replace these lines (currently ~376 and ~395-396):

```python
            is_rl = _is_red_letter(book.directory, ch_num, verse_num)
```
with:
```python
            desc = _get_red_letter_desc(book.directory, ch_num, verse_num)
```

and replace:
```python
                if is_rl:
                    lettrine_text = _apply_red_letter_quotes(lettrine_text)
```
with:
```python
                lettrine_text = _render_red_letter(lettrine_text, desc, rl_state)
```

- [ ] **Step 3: Replace the normal-verse red-letter call**

Replace (currently ~408-409):
```python
                if is_rl:
                    text = _apply_red_letter_quotes(text)
```
with:
```python
                text = _render_red_letter(text, desc, rl_state)
```

> Note: `_render_red_letter` is now called for EVERY verse (not just flagged
> ones). With `desc is None` it closes any open red (Jesus stopped) and returns
> the text unchanged — this is what makes continuation/termination correct.

- [ ] **Step 4: Smoke-test generation from cache (no network)**

Run:
```bash
rm -rf /tmp/net_rl && python3 scripts/generate_bible.py --books matthew \
  --output-dir /tmp/net_rl --cache-dir data/net_bible_cache 2>&1 | tail -3
```
Expected: ends with `Done!`, no traceback.

- [ ] **Step 5: Commit**

```bash
git add scripts/latex_generator.py
git commit -m "feat(red-letter): thread per-chapter state through verse loop"
```

---

## Task 7: Integration assertions on real NET data

Verify every flagged verse contributes red and toggles balance per chapter.

**Files:**
- Test: `tests/test_red_letter.py`

- [ ] **Step 1: Add an integration test that generates Matthew & John from cache**

Append to `tests/test_red_letter.py` (before the `if _failures:` block):

```python
print("integration: generate Matthew & John from cache")
import json as _json, glob as _glob, re as _re

_root = os.path.join(os.path.dirname(__file__), "..")

def _gen(book_dir):
    import bible_config
    book = next(b for b in bible_config.BOOKS if b.directory == book_dir)
    chapters = {}
    for f in _glob.glob(os.path.join(_root, "data", "net_bible_cache",
                                     f"{book_dir}_*.json")):
        ch = int(_re.search(rf"{book_dir}_(\d+)\.json", f).group(1))
        h = _json.load(open(f))
        verses = h if isinstance(h, list) else h.get("verses", [])
        chapters[ch] = verses
    return lg.generate_book_tex(book, chapters)

for bd in ("matthew", "john"):
    tex = _gen(bd)
    on = tex.count("\\redletteron")
    off = tex.count("\\redletteroff")
    check(f"{bd}: emits red letter", on > 50, f"on={on}")
    check(f"{bd}: toggles balanced", on == off, f"on={on} off={off}")
```

- [ ] **Step 2: Run the full test suite**

Run: `python3 tests/test_red_letter.py`
Expected: PASS, with Matthew/John each showing balanced `on == off` and `on > 50`.

- [ ] **Step 3: Manually confirm the Sermon on the Mount is now red**

Run:
```bash
rm -rf /tmp/net_rl && python3 scripts/generate_bible.py --books matthew \
  --output-dir /tmp/net_rl --cache-dir data/net_bible_cache >/dev/null 2>&1
python3 -c "
t=open('/tmp/net_rl/matthew/matthew.tex').read()
i=t.find('Matthew 5:4'); print(t[i-40:i+160])"
```
Expected: the verse-4 region shows `\redletteron` wrapping the beatitude text
(previously it rendered black).

- [ ] **Step 4: Commit**

```bash
git add tests/test_red_letter.py
git commit -m "test(red-letter): integration assertions on Matthew & John"
```

---

## Task 8: Visual verification

**Files:** none (manual check)

- [ ] **Step 1: Compile a Matthew 5 snippet and render to PNG**

Reuse the minimal-document approach from `tests/redletter_visual_check.tex`:
extract the generated Matthew 5 verses 1–6 from `/tmp/net_rl/matthew/matthew.tex`
into a standalone `scripture` document (preamble copied from
`tests/redletter_visual_check.tex`, swapping the body), then:

```bash
TEXINPUTS=".:./tests:" lualatex -interaction=nonstopmode -halt-on-error \
  -output-directory=tests tests/_net_rl_check.tex >/dev/null 2>&1
pdftoppm -png -r 150 tests/_net_rl_check.pdf tests/_net_rl_check
```

- [ ] **Step 2: Inspect the PNG**

Open `tests/_net_rl_check-1.png`. Confirm: every Beatitude (vv. 3–12) is red,
verse numbers are black, and red flows across the verse boundaries.

- [ ] **Step 3: Clean up build artifacts**

```bash
rm -f tests/_net_rl_check.* tests/_net_rl_check-1.png
```

No commit (verification only).

---

## Task 9: Regenerate data and clean up dead code

**Files:**
- Modify: `scripts/latex_generator.py` (remove now-unused symbols if any remain)
- Regenerate: `data/red_letter_verses.json`

- [ ] **Step 1: Confirm no references remain to removed helpers**

Run: `grep -n "_is_red_letter\|_apply_red_letter_quotes" scripts/*.py`
Expected: no output (both fully replaced).

- [ ] **Step 2: Ensure data file is current**

Run: `python3 scripts/build_red_letter_data.py`
Expected: per-book summaries print; `data/red_letter_verses.json` written with `_format: 2`.

- [ ] **Step 3: Final full test run**

Run: `python3 tests/test_red_letter.py && python3 tests/test_latex_escaping.py`
Expected: both print `All tests passed.`

- [ ] **Step 4: Commit (force-add gitignored data if committing it)**

```bash
git add scripts/latex_generator.py
git add -f data/red_letter_verses.json
git commit -m "chore(red-letter): regenerate v2 data; remove dead helpers"
```

---

## Self-Review Notes

- **Spec coverage:** enriched data model (Task 2-3), depth-based nested handling
  (Task 4 + nesting test), mixed-speaker `opens` (Tasks 2,4), `starts_in_jesus`
  continuation (Tasks 2,4), chapter-level threading (Task 6), apostrophes (single
  quotes never tracked → covered implicitly; the mixed-speaker test uses `don't`),
  edge fallbacks (`opens[k]` default False in Task 4; legacy-format guard in Task 5),
  testing + visual (Tasks 7-8), migration (Task 9). All covered.
- **Type consistency:** descriptor shape `{"opens": list[bool], "starts_in_jesus": bool}`
  is identical in builder output (Task 2/3), renderer input (Task 4), and lookup
  (Task 5). `_RLState` fields (`in_jesus`, `depth`, `open_depth`) are consistent
  across Tasks 4 and 6. Function names: `_clean_web_verse`, `parse_verse_descriptor`,
  `parse_usfm_for_descriptors`, `_get_red_letter_desc`, `_RLState`, `_render_red_letter`.
- **Out of scope (unchanged):** ESV path, word-level alignment, books beyond the six.
