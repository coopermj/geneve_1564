import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from latex_generator import _split_poetry_segments

ISA_56_3 = ('<p class="poetry">No foreigner who becomes a follower of the Lord'
            ' should say,<p class="poetry">"The Lord will certainly exclude me'
            ' from his people."<p class="poetry">The eunuch should not say,'
            '<p class="poetry">"Look, I am like a dried-up tree." </p>')

ISA_56_4 = ('<p class="bodytext">For this is what the Lord says:'
            '<p class="poetry">"For the eunuchs who observe my Sabbaths </p>')

PSA_101_1 = ('<p class="psasuper">A psalm of David.'
             '<p class="poetry">I will sing about loyalty and justice. </p>')

CONTINUATION = 'They will be spread out and exposed to the sun. </p>'

AMOS_BREAK = ('<p class="poetrybreak">"Certainly when I punish Israel,'
              '<p class="poetry">I will destroy Bethel\'s altars. </p>')


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


# ---------------------------------------------------------------------------
# Task-3 emission tests
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

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
    # No drop-cap \lettrine{}{} command inside the poetry block
    assert "\\lettrine{" not in tex.split("\\begin{poetry}")[1]
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
    assert "\\textit{A psalm of David.}" in tex


def test_mixed_cont_and_line_same_verse():
    # verse 2 has lead text (continuation) AND a <p> line
    chapters = {56: [
        {"verse": "1", "text": '<p class="poetry">First verse line. </p>'},
        {"verse": "2", "text": 'lead continues. <p class="poetry">then a new line. </p>'},
    ]}
    tex = _gen(chapters)
    body = tex.split("\\begin{poetry}")[1]
    source_lines = body.split("\n")
    # \vs{2} must appear mid-line (not at start of a source line)
    assert not any(l.startswith("\\vs{2}") for l in source_lines)
    assert "\\vs{2}" in body
    # "then a new line" must start its own flush source line
    new_line_idx = next(i for i, l in enumerate(source_lines) if "then a new line" in l)
    assert source_lines[new_line_idx - 1] == ""
