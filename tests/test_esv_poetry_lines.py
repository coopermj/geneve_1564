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
