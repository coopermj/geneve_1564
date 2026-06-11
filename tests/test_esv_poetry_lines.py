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
    tex = _convert(PSALM_HTML)
    assert "A Psalm of David, when he fled" in tex
    i_ch = tex.index("\\ch{3}")
    i_title = tex.index("A Psalm of David")
    assert i_title > i_ch


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
