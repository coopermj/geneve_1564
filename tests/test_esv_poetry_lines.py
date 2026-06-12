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
    return "\n".join(esv._process_chapter_html(html, ch, book,
                                               is_first_chapter=False))


def test_psalm_title_emitted_italic_after_ch():
    r"""Title is still after \ch{3} in string order (now on the \ch line itself)."""
    tex = _convert(PSALM_HTML)
    assert "A Psalm of David, when he fled" in tex
    i_ch = tex.index("\\ch{3}")
    i_title = tex.index("A Psalm of David")
    assert i_title > i_ch


def test_psalm_title_rides_ch_line_not_verse_text():
    """When a psalm title is pending, the \\ch line carries the title (not verse 1 text)."""
    tex = _convert(PSALM_HTML)
    ch_line = next(l for l in tex.split("\n") if "\\ch{3}" in l)
    # The title text must be ON the \ch line
    assert "A Psalm of David" in ch_line
    # Verse 1 text must NOT be on the \ch line
    assert "how many are my foes" not in ch_line


def test_verse1_text_as_flush_line_after_title():
    """Verse 1 first piece (O LORD...) appears as a flush line (preceded by blank)."""
    tex = _convert(PSALM_HTML)
    lines = tex.split("\n")
    # Find the "O LORD" line
    olord_idx = next(i for i, l in enumerate(lines) if "O \\textsc{Lord}" in l and "how many" in l)
    # It must be preceded by a blank line (flush = blank + content)
    assert lines[olord_idx - 1] == "", (
        f"Expected blank before 'O LORD' line, got: {repr(lines[olord_idx - 1])}")


def test_couplet_indent_restored():
    """'Many are rising' (indent piece) directly follows 'O LORD' — no blank between, couplet intact."""
    tex = _convert(PSALM_HTML)
    lines = tex.split("\n")
    olord_idx = next(i for i, l in enumerate(lines) if "O \\textsc{Lord}" in l and "how many" in l)
    rising_idx = next(i for i, l in enumerate(lines) if "Many are rising" in l)
    # The indent piece must be the very next line after its flush partner
    assert rising_idx == olord_idx + 1, (
        f"Expected 'Many are rising' at line {olord_idx + 1}, got {rising_idx}. "
        f"Intervening lines: {lines[olord_idx:rising_idx + 1]}")


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


def test_vs_before_markboth_in_poetry():
    tex = _convert(PSALM_HTML)
    line = next(l for l in tex.split("\n") if l.startswith("\\vs{2}"))
    assert line.index("\\vs{2}") < line.index("\\markboth")


def test_no_stretchable_space_after_markboth_in_poetry():
    r"""After \vs{N}\markboth{...}{...} there must be NO literal space before
    the verse text — any such space is justification-stretchable and causes
    visible verse-number gap wobble.  The cleanup regex must match the
    vs+markboth pair, not just bare \vs{N}.
    """
    tex = _convert(PSALM_HTML)
    line = next(l for l in tex.split("\n") if l.startswith("\\vs{2}"))
    # Immediately after the closing brace of the second markboth arg there
    # must be a non-space character (the verse text begins immediately).
    assert re.search(r'\\vs\{2\}\\markboth\{[^}]*\}\{[^}]*\}\S', line), (
        f"stretchable space found after markboth in poetry line: {repr(line)}"
    )


# ---------------------------------------------------------------------------
# Non-poetry chapter: line spans flattened, no sentinels, no crash
# ---------------------------------------------------------------------------

ROMANS_PROSE_HTML = '''<p class="starts-chapter"><b class="chapter-num" id="v1">1:1&nbsp;</b>Paul, a servant of Christ Jesus, <span class="line">called to be an apostle,</span><br /><span class="indent line">set apart for the gospel of God,</span></p>'''


def _convert_romans(html, ch=1):
    book = get_book_by_name("romans")
    return "\n".join(esv._process_chapter_html(html, ch, book,
                                               is_first_chapter=True))


def test_non_poetry_line_spans_flattened_no_sentinels():
    """Non-poetry chapter: line spans produce no sentinels, prose is intact."""
    tex = _convert_romans(ROMANS_PROSE_HTML)
    # No sentinel bytes must appear
    assert "\x05" not in tex and "\x06" not in tex
    # The prose text must appear (flattened)
    assert "called to be an apostle" in tex
    assert "set apart for the gospel" in tex
    # Chapter heading must appear
    assert "\\ch{1}" in tex


# ---------------------------------------------------------------------------
# Finding 2 — h3 section heading in poetry chapter
# ---------------------------------------------------------------------------

def test_h3_heading_in_poetry_output():
    """The h3 'Save Me, O My God' heading appears inside the section-heading wrapper."""
    tex = _convert(PSALM_HTML)
    # Must contain the heading text inside \small\itshape block
    assert "Save Me, O My God" in tex
    assert "\\small\\itshape Save Me, O My God" in tex


# ---------------------------------------------------------------------------
# Finding 3 — no-title poetry chapter start
# ---------------------------------------------------------------------------

# PSALM_HTML stripped of its h4 title — chapter starts directly with verse text.
PSALM_HTML_NO_TITLE = '''<h3 id="x">Save Me, O My God</h3>
<p class="block-indent"><span class="begin-line-group"></span>
<span id="a" class="line"><b class="chapter-num" id="v1">3:1&nbsp;</b>&nbsp;&nbsp;O LORD, how many are my foes!</span><br /><span id="a" class="indent line">&nbsp;&nbsp;&nbsp;&nbsp;Many are rising against me;</span><br /><span class="end-line-group"></span>
</p>'''


def test_no_title_chapter_start_ch_carries_first_verse():
    r"""Without a psalm title, \ch{3} line carries the first verse piece."""
    tex = _convert(PSALM_HTML_NO_TITLE)
    ch_line = next(l for l in tex.split("\n") if "\\ch{3}" in l)
    assert "how many are my foes" in ch_line


def test_no_title_chapter_start_indent_partner_consecutive():
    """The indent partner ('Many are rising') follows directly after the \\ch line."""
    tex = _convert(PSALM_HTML_NO_TITLE)
    lines = tex.split("\n")
    ch_idx = next(i for i, l in enumerate(lines) if "\\ch{3}" in l)
    # Next non-empty line after \ch must be the indent partner (no blank between)
    following = lines[ch_idx + 1]
    assert "Many are rising" in following, (
        f"Expected indent partner right after \\ch line, got: {repr(following)}")


# ---------------------------------------------------------------------------
# Finding 1 — Psalm 119 acrostic headings
# ---------------------------------------------------------------------------

# Two stanzas separated by an acrostic heading: Beth between Aleph stanza and
# the next stanza. The block layout mirrors what the ESV splitter produces.
PSALM_119_ACROSTIC_HTML = '''\
<h4 id="aleph" class="psalm-acrostic-title">Aleph</h4>
<p class="block-indent"><span class="begin-line-group"></span>
<span id="a" class="line"><b class="chapter-num" id="v1">119:1&nbsp;</b>&nbsp;&nbsp;Blessed are those whose way is blameless,</span><br /><span id="a" class="indent line">&nbsp;&nbsp;&nbsp;&nbsp;who walk in the law of the LORD!</span><br /><span class="end-line-group"></span>
</p><h4 id="beth" class="psalm-acrostic-title">Beth</h4>
<p class="block-indent"><span class="begin-line-group"></span>
<span id="b" class="line"><b class="verse-num" id="v9">9&nbsp;</b>&nbsp;&nbsp;How can a young man keep his way pure?</span><br /><span id="b" class="indent line">&nbsp;&nbsp;&nbsp;&nbsp;By guarding it according to your word.</span><br /><span class="end-line-group"></span>
</p>'''


def _convert_ps119(html, ch=119):
    book = get_book_by_name("psalms")
    return "\n".join(esv._process_chapter_html(html, ch, book,
                                               is_first_chapter=False))


def test_acrostic_heading_appears_in_output():
    """Acrostic heading 'Beth' appears in output."""
    tex = _convert_ps119(PSALM_119_ACROSTIC_HTML)
    assert "Beth" in tex


def test_acrostic_heading_in_small_itshape_wrapper():
    """Acrostic heading is emitted inside the \\small\\itshape heading block."""
    tex = _convert_ps119(PSALM_119_ACROSTIC_HTML)
    assert "\\small\\itshape Beth" in tex


def test_acrostic_heading_between_stanzas_not_glued_to_line():
    """'Beth' appears between the two stanzas and is NOT glued onto a verse line."""
    tex = _convert_ps119(PSALM_119_ACROSTIC_HTML)
    lines = tex.split("\n")
    # Stanza 1 text
    aleph_idx = next(i for i, l in enumerate(lines) if "blameless" in l)
    # Beth heading
    beth_idx = next(i for i, l in enumerate(lines) if "Beth" in l and "\\small\\itshape" in l)
    # Stanza 2 text
    beth_stanza_idx = next(i for i, l in enumerate(lines) if "young man" in l)
    assert aleph_idx < beth_idx < beth_stanza_idx, (
        f"Expected aleph({aleph_idx}) < beth_heading({beth_idx}) < beth_stanza({beth_stanza_idx})"
    )
    # Beth must NOT appear on the same line as verse text
    beth_heading_line = lines[beth_idx]
    assert "blameless" not in beth_heading_line
    assert "young man" not in beth_heading_line


# ---------------------------------------------------------------------------
# Fix 1 — margin_note not dropped when ch_match + no psalm title + 1 line piece
# ---------------------------------------------------------------------------

# Single-line poetry chapter-open with a footnote in the only line span.
# emit_pieces ends up empty (the one piece rides the \ch line), so the
# margin note must be appended to the \ch line itself.
_SINGLE_LINE_FN_HTML = '''\
<p class="block-indent"><span class="begin-line-group"></span>
<span id="a" class="line"><b class="chapter-num" id="v1">3:1&nbsp;</b>&nbsp;&nbsp;O LORD, how many are my foes!<sup class="footnote"><a href="#fb1-1" id="fb1-1">1</a></sup></span><br /><span class="end-line-group"></span>
</p>
<div class="footnotes"><span class="footnote"><span class="footnote-label"><a href="#fb1-1" id="fb1-1">[1]</a></span><span class="footnote-ref">3:1 </span>Or <i>foes indeed</i></span></p></div>'''


def test_single_line_ch_match_margin_note_not_dropped():
    r"""\marginnote must appear in output when the chapter-open block has exactly
    one line piece (so emit_pieces is empty and the margin note would otherwise
    be silently lost).
    """
    tex = _convert(_SINGLE_LINE_FN_HTML)
    assert "\\marginnote" in tex, (
        "margin note was silently dropped when emit_pieces is empty"
    )


# ---------------------------------------------------------------------------
# (e) Prose chapter: block-indent with line spans → inline poetry env
# ---------------------------------------------------------------------------

# 1 Cor 15:54 – prose paragraph then a block-indent with one line span.
# Verse 54 starts in the prose paragraph; the OT quote is in the block.
COR15_PART1_HTML = '''\
<p id="p46015053_06-1"><b class="verse-num" id="v46015053-1">53&nbsp;</b>For this perishable body must put on the imperishable. <b class="verse-num" id="v46015054-1">54&nbsp;</b>When the perishable puts on the imperishable, then shall come to pass the saying that is written:</p>
<p class="block-indent"><span class="begin-line-group"></span>
<span id="p46015054_16-1" class="line">&nbsp;&nbsp;"Death is swallowed up in victory."</span><br />
<span class="end-line-group"></span>
</p>'''

# 1 Cor 15:55 – entirely a block-indent with two line spans; verse num inside first span.
COR15_55_HTML = '''\
<p class="block-indent"><span class="begin-line-group"></span>
<span id="p46015055_16-1" class="line"><b class="verse-num" id="v46015055-1">55&nbsp;</b>&nbsp;&nbsp;"O death, where is your victory?</span><br /><span id="p46015055_16-1" class="indent line">&nbsp;&nbsp;&nbsp;&nbsp;O death, where is your sting?"</span><br /><span class="end-line-group"></span>
</p>'''

# Prose chapter fixture: verse 1 (plain prose) + verse 53/54 (inline quote)
COR15_PROSE_CHAPTER_HTML = '''\
<p class="starts-chapter"><b class="chapter-num" id="v46015001-1">15:1&nbsp;</b>Now I would remind you, brothers, of the gospel I preached to you.</p>
''' + COR15_PART1_HTML

# Prose chapter fixture for verse 55 (starts a new block after prior prose)
COR15_55_CHAPTER_HTML = '''\
<p class="starts-chapter"><b class="chapter-num" id="v46015001-1">15:1&nbsp;</b>Now I would remind you, brothers, of the gospel I preached to you.</p>
''' + COR15_55_HTML

# Poetry chapter fixture: Psalm 23 (a poetry chapter) with line spans
PSALM23_POETRY_HTML = '''\
<p class="block-indent"><span class="begin-line-group"></span>
<span id="a" class="line"><b class="chapter-num" id="v1">23:1&nbsp;</b>&nbsp;&nbsp;The LORD is my shepherd;</span><br /><span id="a" class="indent line">&nbsp;&nbsp;&nbsp;&nbsp;I shall not want.</span><br />
<span class="end-line-group"></span>
</p>'''

# Block with a footnote on the one line span (single-piece edge case)
COR15_SINGLE_LINE_FN_HTML = '''\
<p id="p46015001_06-1"><b class="chapter-num" id="v46015001-1">15:1&nbsp;</b>Prose text before the quote.</p>
<p class="block-indent"><span class="begin-line-group"></span>
<span id="p46015054_16-1" class="line">&nbsp;&nbsp;"Death is swallowed up in victory."<sup class="footnote"><a href="#fb1-1" id="fb1-1">1</a></sup></span><br />
<span class="end-line-group"></span>
</p>
<div class="footnotes"><span class="footnote"><span class="footnote-label"><a href="#fb1-1" id="fb1-1">[1]</a></span><span class="footnote-ref">15:54 </span>Or <i>swallowed forever</i></span></p></div>'''


def _convert_prose(html, ch=15, book_name="1 corinthians"):
    """Convert for a non-poetry chapter (1 Corinthians 15 is prose)."""
    book = get_book_by_name(book_name)
    return "\n".join(esv._process_chapter_html(html, ch, book,
                                               is_first_chapter=False))


def _convert_poetry(html, ch=23, book_name="psalms"):
    """Convert for a poetry chapter."""
    book = get_book_by_name(book_name)
    return "\n".join(esv._process_chapter_html(html, ch, book,
                                               is_first_chapter=False))


def test_prose_chapter_block_indent_produces_inline_poetry_env():
    """(e) Prose chapter with block-indent line spans → \\begin{poetry}...\\end{poetry}."""
    tex = _convert_prose(COR15_PROSE_CHAPTER_HTML)
    # Must contain exactly one poetry env for the quote block
    assert tex.count("\\begin{poetry}") == 1, (
        f"Expected 1 begin{{poetry}}, got {tex.count(chr(92)+'begin{poetry}')}")
    assert tex.count("\\end{poetry}") == 1
    # The quote must be inside the env
    idx_begin = tex.index("\\begin{poetry}")
    idx_end = tex.index("\\end{poetry}")
    body = tex[idx_begin:idx_end]
    assert "swallowed up in victory" in body, "line text must be inside poetry env"
    # No sentinel leaks
    assert "\x05" not in tex and "\x06" not in tex


def test_prose_chapter_vs_inside_env_when_verse_starts_in_block():
    """(e) When a verse starts inside the block-indent, \\vs{N} is the first
    token of the first line inside the env (\\vs-first layout)."""
    tex = _convert_prose(COR15_55_CHAPTER_HTML)
    assert tex.count("\\begin{poetry}") == 1
    idx_begin = tex.index("\\begin{poetry}")
    idx_end = tex.index("\\end{poetry}")
    body = tex[idx_begin:idx_end]
    # \vs{55} must be inside the env
    assert "\\vs{55}" in body, "\\vs{55} must be inside the poetry env"
    # The second line directly follows the first (no blank between → 1em indent)
    lines_in_body = body.split("\n")
    vic_idx = next(i for i, l in enumerate(lines_in_body) if "your victory" in l)
    sting_idx = next(i for i, l in enumerate(lines_in_body) if "your sting" in l)
    assert sting_idx == vic_idx + 1, (
        f"Second poetry line must directly follow first; got {lines_in_body[vic_idx:sting_idx+1]}"
    )


def test_poetry_chapter_no_nested_env():
    """(f) Poetry chapter: \\begin{poetry} count == 1 (no nested inner env)."""
    tex = _convert_poetry(PSALM23_POETRY_HTML)
    count = tex.count("\\begin{poetry}")
    assert count == 1, (
        f"Poetry chapter must have exactly 1 begin{{poetry}}, got {count}"
    )


def test_prose_chapter_margin_note_on_last_line():
    """(g) margin_note for a single-piece block rides the one emitted line inside env."""
    tex = _convert_prose(COR15_SINGLE_LINE_FN_HTML)
    assert tex.count("\\begin{poetry}") == 1
    idx_begin = tex.index("\\begin{poetry}")
    idx_end = tex.index("\\end{poetry}")
    body = tex[idx_begin:idx_end]
    # The margin note must be INSIDE the env (on the one poetry line)
    assert "\\marginnote" in body, (
        "margin_note must be on the last line inside the inline poetry env"
    )


def test_guard_chapter_num_in_line_span_no_inner_env():
    """Guard: when chapter-num <b> is inside a line span (verse 1 is itself a
    poetry line), flatten that block — do NOT emit an inner poetry env, since
    it would collide with the \\ch + lettrine emission.
    The guard case is prose chapters like Isaiah 16/18, Zechariah 11,
    Deuteronomy 32, Jeremiah 12 (12 chapters total in esv_cache).
    """
    # Isaiah 16:1 — chapter-num inside line span (prose chapter; not in poetry_sections)
    isa16_html = '''\
<p class="block-indent"><span class="begin-line-group"></span>
<span id="p23016001_01-1" class="line"><b class="chapter-num" id="v23016001-1">16:1&nbsp;</b>&nbsp;&nbsp;Send the lamb to the ruler of the land,</span><br />
<span id="p23016001_01-1" class="indent line">&nbsp;&nbsp;&nbsp;&nbsp;to the mount of the daughter of Zion.</span><br />
<span class="end-line-group"></span>
</p>'''
    book = get_book_by_name("isaiah")
    tex = "\n".join(esv._process_chapter_html(isa16_html, 16, book, is_first_chapter=False))
    # Must NOT emit a \begin{poetry} env — block is flattened (it's a chapter-start block)
    assert "\\begin{poetry}" not in tex, (
        "Must not emit inline poetry env when chapter-num is in a line span (chapter-start block)"
    )
    # The verse text must still appear (flattened; lettrine wraps first word)
    assert "lamb to the ruler" in tex
    # The \ch{16} heading must also appear
    assert "\\ch{16}" in tex
