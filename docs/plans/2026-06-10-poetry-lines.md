# True Poetic Lines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render Bible poetry as real poetic lines (hemistichs) instead of whole verses wrapped as single paragraphs with a 4em run-over indent.

**Architecture:** Both source corpora carry true line structure that the generators currently flatten: NET marks each poetic line with `<p class="poetry">` (plus special classes `psasuper`, `lamhebrew`, `sosspeaker`, `poetrybreak`, and `bodytext` prose interleaved); ESV marks lines with `<span class="line">` / `<span class="indent line">` separated by `<br/>`. The scripture package's `poetry` environment input model (verified empirically): each source line is one poetic line; a line directly after another is indented `poetry/indent` (1em); a blank line resets to flush; wrapped text indents `poetry/bigindent`; `\vs{N}` at line start hangs the verse number left. We split verses into line segments before emission, thread red-letter state through with `\x05` sentinels, and emit one source line per poetic line.

**Decisions (user-approved):**
- NET/Geneva: all poetic lines flush-left (source has no indent levels) — blank line before every line.
- ESV: real two-level indents from `line` vs `indent line` (also `indent-2`, `declares`, `psalm-doxology` → indent).
- NET/Geneva poetry chapters: replace the 2-line drop cap with a **colored initial at normal size** (EB Garamond Initials font, body size).
- `poetry/bigindent=2em` in all four editions (run-over indent; default 4em too wide for 59mm columns).
- ESV psalm superscriptions (`<h4 class="psalm-title">`, currently silently dropped) are restored as italic lines after the chapter heading.
- Out of scope (follow-up): OT-quote poetry blocks inside *prose* chapters (NET `otpoetry`, ESV line-groups in NT prose). They keep today's flattened-prose rendering; sentinels must not leak there.

**Tech Stack:** Python 3 generators (`scripts/latex_generator.py`, `scripts/esv_latex_generator.py`), LuaLaTeX + scripture v2.3, pytest, PyMuPDF for quantitative verification.

**Key empirical facts (already verified — do not re-derive):**
- Probe (`poetry_probe.tex` at repo root) confirmed: consecutive lines indent 1em; blank line resets flush; wraps at leftmargin+bigindent; `\vs` line is flush with number hung left; blank lines add no vertical space.
- 7,509 NET poetry verses; 319 start WITHOUT a `<p>` tag → their first segment **continues the previous poetic line** (append to previous output line, `\vs` mid-line is supported by the package).
- Python `\s+` does not match `\x05`/`\x06` control chars → sentinels survive whitespace collapsing.
- scripture's `\redletteron` is a color switch + global bool with re-assertion — safe across paragraph (line) boundaries.
- In the poetry env's obeylines EOL handler, the *first token* of a line is peeked: `\vs` gets flush+hung-number treatment, `\extraskip` inserts stanza space without ending a line. `\markboth` as first token defeats `\vs` detection → emit `\vs{N}` FIRST, `\markboth` immediately after it.

---

### Task 1: `poetry/bigindent=2em` in all editions + extraskip probe

**Files:**
- Modify: `esv_bible.tex`, `net_reading.tex`, `net_notes.tex`, `geneva_bible.tex` (the `\scripturesetup{...}` block in each)
- Modify: `poetry_probe.tex` (repo root, already exists)

- [ ] **Step 1: Add the key to each edition.** In each of the four `.tex` files, inside `\scripturesetup{...}`, directly after the `poetry/verse/sep=0.3em,` line, add:

```latex
  poetry/bigindent=2em,
```

- [ ] **Step 2: Verify `\extraskip` semantics in the probe.** In `poetry_probe.tex`, between the `DDD/EEE` group and the `\vs{4}` group, insert a stanza break:

```latex
\extraskip
\vs{4}FFF first line of verse four,
```

(i.e. the existing blank line, then a line containing only `\extraskip`, then the `\vs{4}` line). Compile and measure:

```bash
OSFONTDIR=fonts lualatex -interaction=nonstopmode poetry_probe.tex
python3 - <<'EOF'
import fitz
doc = fitz.open('poetry_probe.pdf')
ys = [(l['bbox'][1], ''.join(s['text'] for s in l['spans']))
      for b in doc[0].get_text('dict')['blocks'] for l in b['lines']]
for y, t in ys: print(f"{y:7.1f} {t!r}")
EOF
```

Expected: the gap above `4 FFF` is larger than the normal ~15.5pt line step (extraskip default `\medskipamount`), and wrapped `EEE` run-over now sits at leftmargin+2em (x0 ≈ 61.5pt instead of 87.4pt). If `\extraskip` errors or adds no space, note it and use a blank line + `\addvspace{\medskipamount}` line instead — but verify before deviating.

- [ ] **Step 3: Commit**

```bash
git add esv_bible.tex net_reading.tex net_notes.tex geneva_bible.tex poetry_probe.tex
git commit -m "feat(poetry): bigindent=2em in all editions; probe verifies extraskip"
```

---

### Task 2: NET `_split_poetry_segments` (TDD)

**Files:**
- Modify: `scripts/latex_generator.py` (add function near `_strip_html_tags`)
- Create: `tests/test_poetry_lines.py`

- [ ] **Step 1: Write failing tests.** Create `tests/test_poetry_lines.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from latex_generator import _split_poetry_segments

ISA_56_3 = ('<p class="poetry">No foreigner who becomes a follower of the Lord'
            ' should say,<p class="poetry">“The Lord will certainly exclude me'
            ' from his people.”<p class="poetry">The eunuch should not say,'
            '<p class="poetry">“Look, I am like a dried-up tree.” </p>')

ISA_56_4 = ('<p class="bodytext">For this is what the Lord says:'
            '<p class="poetry">“For the eunuchs who observe my Sabbaths </p>')

PSA_101_1 = ('<p class="psasuper">A psalm of David.'
             '<p class="poetry">I will sing about loyalty and justice. </p>')

CONTINUATION = 'They will be spread out and exposed to the sun. </p>'

AMOS_BREAK = ('<p class="poetrybreak">“Certainly when I punish Israel,'
              '<p class="poetry">I will destroy Bethel’s altars. </p>')


def test_plain_poetry_lines():
    segs = _split_poetry_segments(ISA_56_3)
    assert [k for k, _ in segs] == ["line", "line", "line", "line"]
    assert "No foreigner" in segs[0][1]
    assert "dried-up tree" in segs[3][1]
    # closing </p> must not survive in any segment
    assert all("</p>" not in h for _, h in segs)


def test_mixed_prose_and_poetry():
    segs = _split_poetry_segments(ISA_56_4)
    assert [k for k, _ in segs] == ["prose", "line"]
    assert "For this is what" in segs[0][1]


def test_psalm_superscription():
    segs = _split_poetry_segments(PSA_101_1)
    assert segs[0][0] == "psasuper"
    assert segs[1][0] == "line"


def test_continuation_verse_no_leading_p():
    segs = _split_poetry_segments(CONTINUATION)
    assert segs[0][0] == "cont"
    assert "spread out" in segs[0][1]


def test_poetrybreak():
    segs = _split_poetry_segments(AMOS_BREAK)
    assert [k for k, _ in segs] == ["break", "line"]


def test_speaker_and_lamhebrew_kinds():
    sos = ('<p class="sosspeaker"><b><i>The Beloved:</i></b>'
           '<p class="poetry">Oh, how I wish you would kiss me! </p>')
    lam = ('<p class="lamhebrew"><span class="hebrew">א</span> (<i>Alef</i>)'
           '<p class="poetry">Alas! The city sits alone! </p>')
    assert _split_poetry_segments(sos)[0][0] == "sosspeaker"
    assert _split_poetry_segments(lam)[0][0] == "lamhebrew"
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_poetry_lines.py -v`
Expected: FAIL — `ImportError: cannot import name '_split_poetry_segments'`

- [ ] **Step 3: Implement.** In `scripts/latex_generator.py`, after `_strip_html_tags`:

```python
# Map NET <p class="..."> classes to poetry segment kinds.
_POETRY_CLASS_KINDS = {
    "poetry": "line",
    "otpoetry": "line",
    "poetrybreak": "break",
    "bodytext": "prose",
    "bodyblock": "prose",
    "quote": "prose",
    "paragraphtitle": "prose",
    "psasuper": "psasuper",
    "lamhebrew": "lamhebrew",
    "sosspeaker": "sosspeaker",
}

_P_TAG_RE = re.compile(r'<p class="([^"]*)">')


def _split_poetry_segments(raw_html: str) -> list[tuple[str, str]]:
    """Split a poetry-chapter verse's HTML into (kind, html) segments.

    Each <p class="..."> opens a new segment; text before the first <p>
    is a continuation of the previous poetic line (kind "cont").  Closing
    </p> tags are dropped.  Kinds: line, break, prose, psasuper,
    lamhebrew, sosspeaker, cont.
    """
    html = raw_html.replace("</p>", " ")
    segments: list[tuple[str, str]] = []
    matches = list(_P_TAG_RE.finditer(html))
    lead = html[: matches[0].start()] if matches else html
    if lead.strip():
        segments.append(("cont", lead))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        seg = html[m.end():end]
        if not seg.strip():
            continue
        kind = _POETRY_CLASS_KINDS.get(m.group(1), "line")
        segments.append((kind, seg))
    return segments
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_poetry_lines.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/latex_generator.py tests/test_poetry_lines.py
git commit -m "feat(net): split poetry verses into line segments by p-class"
```

---

### Task 3: NET poetry emission — lines, colored initial, red-letter threading

**Files:**
- Modify: `scripts/latex_generator.py` (the `generate_book_tex` verse loop, currently ~lines 508–589; add helpers `_make_poetry_initial`, `_emit_poetry_verse`)
- Test: `tests/test_poetry_lines.py` (extend)

- [ ] **Step 1: Write failing emission tests.** Append to `tests/test_poetry_lines.py`:

```python
from latex_generator import generate_book_tex
from bible_config import get_book_by_name


def _gen(chapters, book="isaiah"):
    return generate_book_tex(get_book_by_name(book), chapters)


def test_poetry_verse_emits_one_source_line_per_segment():
    # Chapter 56 of Isaiah is a poetry chapter in poetry_sections.json
    chapters = {56: [
        {"verse": "1", "text": '<p class="poetry">First line one. </p>'},
        {"verse": "3", "text": ISA_56_3},
    ]}
    tex = _gen(chapters)
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    lines = body.split("\n")
    # verse 3: \vs first token, then \markboth, then text — flush via blank line
    vs_lines = [l for l in lines if l.startswith("\\vs{3}")]
    assert len(vs_lines) == 1
    assert "\\markboth{Isaiah 56:3}" in vs_lines[0]
    idx = lines.index(vs_lines[0])
    assert lines[idx - 1] == ""          # blank → flush
    # remaining 3 segments each on own line preceded by blank
    assert "The eunuch should not say," in body
    seg_idx = next(i for i, l in enumerate(lines) if "eunuch should not" in l)
    assert lines[seg_idx - 1] == ""


def test_poetry_chapter_start_colored_initial_no_lettrine():
    chapters = {56: [
        {"verse": "1", "text": '<p class="poetry">Promote justice! </p>'},
    ]}
    tex = _gen(chapters)
    assert "\\lettrine" not in tex.split("\\begin{poetry}")[1]
    assert "{\\lettrinefont\\color{majorprophets}P}romote" in tex


def test_continuation_verse_appends_to_previous_line():
    chapters = {56: [
        {"verse": "1", "text": '<p class="poetry">Line one. </p>'},
        {"verse": "2", "text": 'and this continues the line. </p>'},
    ]}
    tex = _gen(chapters)
    body = tex.split("\\begin{poetry}")[1]
    # verse 2 must NOT start a new source line
    assert not any(l.startswith("\\vs{2}") for l in body.split("\n"))
    assert "\\vs{2}" in body  # mid-line


def test_psasuper_italic_line():
    chapters = {1: [
        {"verse": "1", "text": PSA_101_1},
    ]}
    tex = _gen(chapters, book="psalms")
    assert "{\\itshape A psalm of David.}" in tex
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_poetry_lines.py -v`
Expected: new tests FAIL (current code emits one line per verse, with lettrine)

- [ ] **Step 3: Implement helpers.** In `scripts/latex_generator.py` (near `_make_lettrine`; check `_make_lettrine`'s first-char extraction including the `\redletteron ` prefix handling and mirror it):

```python
_HEBREW_RE = re.compile(r"[֐-׿]+\s*")


def _make_poetry_initial(text: str, color: str) -> str:
    """Colored decorative initial at body size (no drop cap).

    Poetry lines are short, separate paragraphs, so a multi-line
    \\lettrine would overlap line 2.  Uses the EB Garamond Initials
    face for the first letter only, colored by book group.
    """
    prefix = ""
    if text.startswith("\\redletteron "):
        prefix = "\\redletteron "
        text = text[len("\\redletteron "):]
    if not text:
        return prefix
    first, rest = text[0], text[1:]
    return f"{prefix}{{\\lettrinefont\\color{{{color}}}{first}}}{rest}"
```

and the per-verse emitter (kind → styled text + line placement):

```python
def _style_poetry_segment(kind: str, text: str) -> str:
    if kind == "lamhebrew":
        text = _HEBREW_RE.sub("", text).strip()
        return f"{{\\itshape {text}}}"
    if kind == "psasuper":
        return f"{{\\itshape {text}}}"
    if kind == "sosspeaker":
        return f"{{\\bfseries\\itshape {text}}}"
    return text


def _emit_poetry_verse(out: list[str], kinds: list[str], texts: list[str],
                       verse_num: int, mark: str, ann_suffix: str,
                       ch_open: str | None, initial_color: str | None) -> None:
    """Append the poetic lines of one verse to *out*.

    ch_open: when set (verse 1), the `\\ch{N} ...\\hypertarget...` prefix —
    the first segment is placed on that same source line and gets the
    colored initial.  Otherwise the first segment opens with \\vs{N}+mark
    (or is appended to the previous line for kind "cont").
    """
    first_emitted = False
    for kind, text in zip(kinds, texts):
        text = text.strip()
        if not text:
            continue
        styled = _style_poetry_segment(kind, text)
        if not first_emitted:
            first_emitted = True
            if ch_open is not None:
                if kind == "line" and initial_color:
                    styled = _make_poetry_initial(text, initial_color)
                out.append(f"{ch_open}{styled}")
            elif kind == "cont":
                out[-1] += f" \\vs{{{verse_num}}}{mark}{styled}"
            else:
                if kind == "break":
                    out.append("\\extraskip")
                out.append("")
                out.append(f"\\vs{{{verse_num}}}{mark}{styled}")
            continue
        if kind == "break":
            out.append("\\extraskip")
        out.append("")
        # ch_open verse may still need the initial if first segment was
        # a superscription (psasuper/lamhebrew) rather than a line
        if ch_open is not None and initial_color and kind == "line":
            styled = _make_poetry_initial(text, initial_color)
            initial_color = None
        out.append(styled)
    if first_emitted and ann_suffix:
        out[-1] += ann_suffix
```

Note: inside `_emit_poetry_verse`, once any segment got the initial, pass/keep `initial_color=None` so only the FIRST `line` segment of verse 1 is decorated (the code above clears it in the loop; also clear it in the `ch_open` first-segment branch when applied).

- [ ] **Step 4: Rewire the poetry branch of `generate_book_tex`.** Replace the current per-verse poetry handling (the `if verse_num == 1:` lettrine path and the `\everypar`/`\parshape=0` paragraph machinery apply ONLY to prose now). New structure inside the `for verse in verses:` loop when `is_poetry`:

```python
            if is_poetry:
                segs = _split_poetry_segments(raw_html)
                texts = [_process_verse_text(h) for _, h in segs]
                joined = _render_red_letter("\x05".join(texts), desc, rl_state)
                texts = joined.split("\x05")
                kinds = [k for k, _ in segs]
                mark = (f"\\markboth{{{book.name} {ch_num}:{verse_num}}}"
                        f"{{{book.name} {ch_num}:{verse_num}}}")
                ch_open = None
                initial_color = None
                if verse_num == 1:
                    lines.append(f"\\markboth{{{book.name} {ch_num}:1}}"
                                 f"{{{book.name} {ch_num}:1}}")
                    if ch_num > 1:
                        lines.append("\\Needspace*{8\\baselineskip}")
                    lines.append(f"\\bookmark[dest={{ch-{book.directory}-{ch_num}}},"
                                 f"level=1]{{{book.name} {ch_num}}}")
                    ch_open = (f"\\ch{{{ch_num}}} \\allowchapbreak"
                               f"\\hypertarget{{ch-{book.directory}-{ch_num}}}{{}}")
                    initial_color = book.group
                _emit_poetry_verse(lines, kinds, texts, verse_num, mark,
                                   ann_suffix, ch_open, initial_color)
                continue
```

The prose path (existing code) is unchanged. Verify `_render_red_letter` passes `\x05` through untouched (it only inspects quote characters — read the function to confirm before relying on it; if it strips unknown chars, fix the sentinel handling there).

Important detail: `\vs{N}` must be the FIRST token on its source line (the obeylines EOL peek gives it the flush + hung-number treatment); `\markboth` goes right after `\vs{N}` with no intervening space.

- [ ] **Step 5: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS (including existing `test_red_letter.py`, `test_latex_annotations.py`)

- [ ] **Step 6: Visual sample — Isaiah 56 + Psalm 101 + Lamentations 1 + Song 1.** Build a sample from cache (pattern after `scripts/sample_margin.py`: reuse `geneva_bible.tex` preamble, `fetch_book` from cache, `generate_book_tex`). Then quantitative check:

```bash
python3 - <<'EOF'
import fitz
doc = fitz.open('sample_poetry.pdf')
xs = {}
for page in doc:
    for b in page.get_text('dict')['blocks']:
        for l in b['lines']:
            x = round(l['bbox'][0])
            xs[x] = xs.get(x, 0) + 1
print(sorted(xs.items()))
EOF
```

Expected: line starts cluster at ~3 x-positions per column (flush, flush+2em run-over, verse-number-hang) — NOT a smear of deep-indented wraps. Render page 1 to PNG and EYEBALL it (`page.get_pixmap(dpi=150).save(...)`) — the detector-only mistake from the margin-notes work must not repeat.

- [ ] **Step 7: Commit**

```bash
git add scripts/latex_generator.py tests/test_poetry_lines.py
git commit -m "feat(net): true poetic lines — flush hemistichs, colored initial, extraskip stanzas"
```

---

### Task 4: ESV — psalm titles + real two-level poetic lines

**Files:**
- Modify: `scripts/esv_latex_generator.py` (block splitter ~line 253, block loop, `_restore_verse`, poetry emission)
- Test: `tests/test_esv_poetry_lines.py` (create)

- [ ] **Step 1: Write failing tests.** Create `tests/test_esv_poetry_lines.py`:

```python
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import esv_latex_generator as esv
from bible_config import get_book_by_name

PSALM_HTML = '''<h3 id="x">Save Me, O My God</h3>
<h4 id="y" class="psalm-title">A Psalm of David, when he fled from Absalom his son.</h4>
<p class="block-indent"><span class="begin-line-group"></span>
<span id="a" class="line"><b class="chapter-num" id="v1">3:1&nbsp;</b>&nbsp;&nbsp;O LORD, how many are my foes!</span><br /><span id="a" class="indent line">&nbsp;&nbsp;&nbsp;&nbsp;Many are rising against me;</span><br /><span id="b" class="line"><b class="verse-num" id="v2">2&nbsp;</b>&nbsp;&nbsp;many are saying of my soul,</span><br /><span id="b" class="declares line">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;says the LORD.</span><br /><span class="end-line-group"></span>
</p>'''


def _convert(html, ch=3):
    book = get_book_by_name("psalms")
    return "\n".join(esv._convert_chapter_html(book, ch, html,
                                               is_first_chapter=False))


def test_psalm_title_emitted_italic_after_ch():
    tex = _convert(PSALM_HTML)
    assert "A Psalm of David, when he fled" in tex
    i_ch = tex.index("\\ch{3}")
    i_title = tex.index("A Psalm of David")
    assert i_title > i_ch
    assert "\\itshape" in tex[i_ch:i_title + 20]


def test_lines_split_flush_and_indent():
    tex = _convert(PSALM_HTML)
    lines = tex.split("\n")
    flush = next(i for i, l in enumerate(lines) if "many are saying" in l)
    # flush line: preceded by blank, begins with \vs{2}
    assert lines[flush].startswith("\\vs{2}")
    assert lines[flush - 1] == ""
    # indent line: directly after its flush partner, no blank between
    ind = next(i for i, l in enumerate(lines) if "Many are rising" in l)
    assert lines[ind - 1] != ""
    # declares → indent (consecutive)
    dec = next(i for i, l in enumerate(lines) if "says the" in l)
    assert lines[dec - 1] != ""


def test_no_nbsp_indentation_left_in_lines():
    tex = _convert(PSALM_HTML)
    for l in tex.split("\n"):
        assert not l.startswith(" "), repr(l)
        assert "\xa0" not in l


def test_sentinels_never_leak_to_output():
    tex = _convert(PSALM_HTML)
    assert "\x05" not in tex and "\x06" not in tex
```

Note: if `_convert_chapter_html` has a different name/signature, adapt the helper — read the function first (it is the block loop shown at `scripts/esv_latex_generator.py:203`).

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_esv_poetry_lines.py -v`
Expected: FAIL (title dropped; one flattened line)

- [ ] **Step 3: Implement.** In `scripts/esv_latex_generator.py`:

(a) Block splitter — include `h4`:

```python
    blocks = re.split(r'(?=<h3\b|<h4\b|<p\b)', body)
```

(b) After the h3 handler, add an h4 psalm-title handler. The title must appear AFTER the `\ch{N}` line, so stash it:

```python
        h4 = re.match(r'<h4[^>]*class="psalm-title"[^>]*>(.*?)</h4>', block)
        if h4:
            t = unescape(re.sub(r'<[^>]+>', '', h4.group(1))).strip()
            t = _escape_latex(_convert_smart_quotes(t))
            pending_psalm_title = f"{{\\itshape {t}}}"
            continue
```

(initialize `pending_psalm_title = ""` before the block loop; when the `ch_match` branch emits the `\ch` line, if `pending_psalm_title` is set, emit `""` then the title line right after the `\ch{...}` line, then clear it.)

(c) Line sentinels — insert BEFORE tag stripping, only for poetry chapters (sentinels must not leak into prose-chapter output):

```python
        if is_poetry:
            para_text = re.sub(
                r'<span[^>]*class="(?:begin|end)-line-group"[^>]*>\s*</span>',
                '', para_text)
            para_text = re.sub(r'<span[^>]*class="line"[^>]*>', '\x05', para_text)
            para_text = re.sub(r'<span[^>]*class="[^"]*\bline\b[^"]*"[^>]*>',
                               '\x06', para_text)
```

(exact class `"line"` first → flush sentinel; any remaining `*line` class — `indent line`, `indent-2 line`, `declares line`, `psalm-doxology line` — → indent sentinel). The generic `<[^>]+>` strip later removes `</span>` and `<br />`. Verify `re.sub(r'\s+', ' ', ...)` does not eat `\x05`/`\x06` (Python `\s` excludes them — already confirmed).

(d) `_restore_verse` ordering for poetry: `\vs{N}` must be the line's first token, so in poetry chapters emit `\vs{v}` BEFORE the `\markboth`:

```python
        def _restore_verse(m: re.Match) -> str:
            v = m.group(1)
            mark = (f"\\markboth{{{book.name} {ch_num}:{v}}}"
                    f"{{{book.name} {ch_num}:{v}}}")
            if is_poetry:
                return f"\\vs{{{v}}}{mark}"
            return f"{mark}\\vs{{{v}}}"
```

(e) Emission — when `is_poetry` and the processed `para_text` contains sentinels, split and emit lines instead of one flat paragraph. Replace the current `else:` (non-ch_match) emission and the ch_match poetry branch:

```python
        def _emit_poetry_lines(text: str, ch_open: str | None) -> None:
            parts = re.split('([\x05\x06])', text)
            lead = parts[0].strip()
            opened = False
            if ch_open is not None:
                # heading line opens with the first piece of text
                first = lead
                rest_pairs = list(zip(parts[1::2], parts[2::2]))
                if not first and rest_pairs:
                    first = rest_pairs[0][1].strip()
                    rest_pairs = rest_pairs[1:]
                lines.append(f"{ch_open}{first}")
                if pending_psalm_title:
                    lines.append("")
                    lines.append(pending_psalm_title)
                opened = True
            else:
                if lead:
                    lines.append("")
                    lines.append(lead)
                rest_pairs = list(zip(parts[1::2], parts[2::2]))
            for sep, seg in rest_pairs:
                seg = seg.strip()
                if not seg:
                    continue
                # \vs must open its source line: a flush segment starting
                # with \vs already does; indent segments keep their place
                if sep == '\x05':
                    lines.append("")
                lines.append(seg)
```

Adapt naming/closure details to the real function body — the structure (blank line before `\x05` pieces, none before `\x06` pieces, `\ch` line carries the first piece, psalm title right after) is the requirement. Clear `pending_psalm_title` after use. The margin-note suffix (`margin_note`) stays appended to the block's LAST emitted line.

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 5: ESV visual sample — Psalm 3 + Amos 1.** Generate Psalms (or just compile the full ESV later; for fast iteration build a one-book sample with the esv preamble). Quantitative: line-start x-positions must show exactly the flush level, the 1em indent level, and ≤2em run-over; "A Psalm of David, when he fled from Absalom" must be present in extracted text. Render a page to PNG and eyeball.

- [ ] **Step 6: Commit**

```bash
git add scripts/esv_latex_generator.py tests/test_esv_poetry_lines.py
git commit -m "feat(esv): true two-level poetic lines + restore psalm superscriptions"
```

---

### Task 5: Full regeneration + builds + verification

**Files:** generated `livres_esv/`, `livres_net/`, `livres_geneva/`; PDFs.

- [ ] **Step 1: Regenerate all editions**

```bash
cd /Users/micahcooper/geneve_1564
python3 scripts/generate.py --edition all
```

- [ ] **Step 2: Build all four (2-pass, fresh aux)** — delete stale `.aux/.toc/.out` first (stale `\newmarginnote` gotcha):

```bash
rm -f *.aux *.toc *.out
for doc in esv_bible net_reading net_notes geneva_bible; do
  OSFONTDIR=fonts lualatex -interaction=nonstopmode $doc.tex
  OSFONTDIR=fonts lualatex -interaction=nonstopmode $doc.tex
  grep -c "^!" $doc.log || true
done
```

Expected: 0 errors each. Page counts WILL grow (Psalms especially) — note the new counts.

- [ ] **Step 3: Verify across books/editions.** For each edition, extract Isaiah 56, Psalm 23, Lamentations 1, Song of Solomon 1 pages; check x-position clustering; render PNGs and eyeball (Lamentations: "(Alef)" italic line present, no missing-glyph boxes; Song: bold-italic speaker lines; Psalm 3 ESV: superscription present; red-letter spot check: a poetry chapter with words of Christ — e.g. NET Matthew 11:17ish if marked, else Luke quotes in Isaiah are N/A — at minimum re-run `tests/test_red_letter.py` and visually check one red-letter poetry passage in the NT if any chapter qualifies, plus Matthew 21 prose regression).

- [ ] **Step 4: Commit any sample scripts; push**

```bash
git add -A scripts/ tests/ && git commit -m "test(poetry): verification samples" && git push origin master
```

---

### Task 6: Geneva margin-note re-convergence

**Files:** `data/corrections_final.json`, `livres_geneva/`, `geneva_bible.pdf`

The poetry reflow moves every annotation anchor after Job. Re-run the anchor-based convergence (resumable; saves corrections every iteration).

- [ ] **Step 1: Run convergence (background — takes hours)**

```bash
python3 scripts/build_annotated.py \
  --corrections-in data/corrections_final.json \
  --corrections-out data/corrections_final.json
```

(Check `build_annotated.py --help` for exact flag names before running.)

- [ ] **Step 2: Verify 0 overlaps reported AND visually inspect** Genesis 1, Psalm 119 spread, Romans 12 (the detector alone is not trusted — render PNGs).

- [ ] **Step 3: Commit data + push**

```bash
git add -f data/corrections_final.json data/note_manifest.json
git commit -m "fix(geneva): re-converge margin notes after poetry-line reflow"
git push origin master
```

---

## Self-review notes

- Spec coverage: bigindent (T1), NET lines+initial+specials (T2–T3), ESV lines+titles (T4), builds+verification (T5), geneva reconvergence (T6). Out-of-scope follow-up (OT quotes in prose chapters) documented in header.
- `_render_red_letter` sentinel passthrough is asserted as a verify-before-rely step (T3 S4).
- Type consistency: `_split_poetry_segments` returns `list[tuple[str, str]]` consumed in T3; `_emit_poetry_verse(out, kinds, texts, verse_num, mark, ann_suffix, ch_open, initial_color)` used as defined.
- ESV test helper name `_convert_chapter_html` flagged as adapt-to-actual-name.
