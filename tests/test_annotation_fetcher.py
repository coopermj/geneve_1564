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
