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
    assert lines[idx - 1] == ""          # blank → verse start is flush
    # remaining 3 segments: line-after-line → CONSECUTIVE source lines
    # (no blank between) so they take the 1em second-half indent, ESV-style
    assert lines[idx + 1] != "" and "exclude me" in lines[idx + 1]
    assert lines[idx + 2] != "" and "eunuch should not" in lines[idx + 2]
    assert lines[idx + 3] != "" and "dried-up tree" in lines[idx + 3]


def test_verse1_line_couplet_indent_after_ch():
    # Verse 1 with two plain line segments: first rides the \ch line, the
    # second follows DIRECTLY (no blank) so it takes the 1em indent —
    # mirroring the ESV no-title chapter start.
    chapters = {56: [
        {"verse": "1", "text": ('<p class="poetry">First hemistich,'
                                '<p class="poetry">second hemistich. </p>')},
    ]}
    tex = _gen(chapters)
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    lines = body.split("\n")
    ch_idx = next(i for i, l in enumerate(lines) if "\\ch{56}" in l)
    assert "First hemistich," in lines[ch_idx]
    assert "second hemistich." in lines[ch_idx + 1]   # consecutive → indent


def test_prose_segment_resets_to_flush():
    # [prose, line, line]: the prose intro is flush, the first poetry line
    # after it starts a NEW unit (flush, blank-preceded), subsequent lines
    # of the verse indent.
    isa_56_4_full = ('<p class="bodytext">For this is what the Lord says:'
                     '<p class="poetry">"For the eunuchs who observe my Sabbaths'
                     '<p class="poetry">and choose what pleases me, </p>')
    chapters = {56: [
        {"verse": "1", "text": '<p class="poetry">Opening line. </p>'},
        {"verse": "4", "text": isa_56_4_full},
    ]}
    tex = _gen(chapters)
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    lines = body.split("\n")
    vs_idx = next(i for i, l in enumerate(lines) if l.startswith("\\vs{4}"))
    assert lines[vs_idx - 1] == ""                       # prose verse start flush
    eun_idx = next(i for i, l in enumerate(lines) if "eunuchs who observe" in l)
    assert lines[eun_idx - 1] == ""                      # line after prose → flush
    assert "choose what pleases" in lines[eun_idx + 1]   # line after line → indent


def test_poetry_chapter_start_plain_no_lettrine_no_initial():
    chapters = {56: [
        {"verse": "1", "text": '<p class="poetry">Promote justice! </p>'},
    ]}
    tex = _gen(chapters)
    body = tex.split("\\begin{poetry}")[1]
    # No drop-cap \lettrine{}{} and no decorated initial — plain text on \ch line
    assert "\\lettrine{" not in body
    assert "\\lettrinefont" not in body
    assert "\\textcolor" not in body
    assert "Promote justice!" in body


def test_verse1_two_segments_second_on_own_line():
    """Verse 1 with psasuper + poetry line: superscription on \\ch line,
    initial-bearing poetry line on its own flush source line below."""
    # Psalms chapter 1, verse 1 has a psasuper + poetry line
    psa_v1 = ('<p class="psasuper">A psalm of David.'
              '<p class="poetry">I will sing about loyalty. </p>')
    chapters = {1: [
        {"verse": "1", "text": psa_v1},
    ]}
    tex = _gen(chapters, book="psalms")
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    source_lines = body.split("\n")

    # The \ch{1} line must contain the psasuper text but NOT the poetry line
    ch_lines = [l for l in source_lines if "\\ch{1}" in l]
    assert len(ch_lines) == 1
    assert "A psalm of David." in ch_lines[0]
    assert "will sing" not in ch_lines[0]

    # The poetry line must appear on its own source line preceded by a blank
    # line, as plain text (no decorated initial).
    sing_idx = next(i for i, l in enumerate(source_lines) if "I will sing about loyalty" in l)
    assert source_lines[sing_idx - 1] == ""
    assert "\\lettrinefont" not in source_lines[sing_idx]


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
    # "then a new line" follows a poetry line (the continuation) directly:
    # consecutive source line → 1em indent, no blank between
    new_line_idx = next(i for i, l in enumerate(source_lines) if "then a new line" in l)
    assert source_lines[new_line_idx - 1] != ""
    assert "\\vs{2}" in source_lines[new_line_idx - 1]


def test_all_decorated_verse_not_dropped():
    """A verse whose ONLY segment is a sosspeaker (decorated kind) must NOT be
    silently dropped.  When ch_open is None and every segment is decorated, the
    pending queue never gets flushed via the normal first_emitted path.
    The fix must emit \\vs{N} + pending as a standalone flush source line.
    """
    # Song of Solomon ch 1 is full_book poetry; verse 2 has no \ch open.
    sos_v2 = '<p class="sosspeaker"><b><i>The Maidens:</i></b> </p>'
    chapters = {1: [
        # verse 1 to open the chapter (gives us a \ch line, consumes ch_open)
        {"verse": "1", "text": '<p class="sosspeaker"><b><i>She:</i></b> <p class="poetry">Let him kiss me. </p>'},
        # verse 2 is ALL sosspeaker — was silently dropped before the fix
        {"verse": "2", "text": sos_v2},
    ]}
    tex = _gen(chapters, book="songofsolomon")
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    source_lines = body.split("\n")
    # The verse 2 text must appear somewhere in the output
    assert "The Maidens:" in body, "sosspeaker text was silently dropped"
    # \vs{2} must appear at the start of a source line (flush line)
    vs2_lines = [l for l in source_lines if l.startswith("\\vs{2}")]
    assert vs2_lines, "\\vs{2} must open its own source line"
    # That source line must be preceded by a blank line
    idx = next(i for i, l in enumerate(source_lines) if l.startswith("\\vs{2}"))
    assert source_lines[idx - 1] == "", "flush line must be preceded by blank line"


def test_break_kind_emits_extraskip():
    """A verse starting with <p class="poetrybreak"> must emit \\extraskip
    immediately before the blank+\\vs{N} pair.
    """
    # Amos is full_book poetry; use chapter 3 verse 14 with AMOS_BREAK text.
    chapters = {3: [
        {"verse": "1", "text": '<p class="poetry">Hear this word. </p>'},
        {"verse": "14", "text": AMOS_BREAK},
    ]}
    tex = _gen(chapters, book="amos")
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    source_lines = body.split("\n")
    # Find the \vs{14} line
    vs14_lines = [(i, l) for i, l in enumerate(source_lines) if "\\vs{14}" in l]
    assert vs14_lines, "\\vs{14} must appear in output"
    idx = vs14_lines[0][0]
    # The line before \vs{14} must be blank (flush separator)
    assert source_lines[idx - 1] == "", "\\vs{14} must be preceded by a blank line"
    # The line before that blank must be \\extraskip
    assert source_lines[idx - 2] == "\\extraskip", (
        f"expected \\extraskip before blank+\\vs{{14}}, got {source_lines[idx-2]!r}"
    )


# ---------------------------------------------------------------------------
# Minor 1 — ann_suffix must not be glued onto a bare \extraskip line
# ---------------------------------------------------------------------------
from latex_generator import _emit_poetry_verse


def test_ann_suffix_not_appended_to_extraskip():
    """When the last emitted output line is a bare \\extraskip (because the
    final segment of a verse has kind 'break' in the subsequent-segments
    branch), the ann_suffix must NOT be appended to that \\extraskip line.
    It must be appended to the last non-extraskip line instead.

    Setup: verse 2 has two segments — a normal 'line' (first, emitted on its
    own source line) then a 'break' (subsequent, emits \\extraskip only).
    After the loop out[-1] == '\\extraskip'; the guard must back-track.
    """
    out: list[str] = []
    # Two segments: first is a 'line' (first_emitted → True, appends text),
    # second is a 'break' (subsequent → appends \\extraskip only).
    kinds = ["line", "break"]
    texts = ["verse text", "stanza break text"]
    _emit_poetry_verse(out, kinds, texts, verse_num=2, mark="",
                       ann_suffix="\\marginnote{note}", ch_open=None)
    # \\extraskip must appear somewhere
    assert "\\extraskip" in out, f"expected \\extraskip in {out}"
    # No \\extraskip line must carry any suffix
    for line in out:
        if line == "\\extraskip":
            assert "\\marginnote" not in line, (
                f"ann_suffix was glued onto \\extraskip: {line!r}"
            )
    # The suffix must appear in the output somewhere (not lost)
    assert any("\\marginnote{note}" in l for l in out), (
        f"ann_suffix was lost when last segment was 'break'; out={out}"
    )


# ---------------------------------------------------------------------------
# Inline poetry blocks in PROSE chapters (NET generator)
# ---------------------------------------------------------------------------

# 1 Cor 15:54 — prose text then one otpoetry line
COR_15_54 = (
    '<st data-num="1161" class="">Now</st> when this perishable puts on the '
    'imperishable, then the saying that is written will happen,'
    '<p class="otpoetry">"Death has been swallowed up in victory."</p>'
)

# 1 Cor 15:55 — entire verse is two otpoetry lines (no leading prose)
COR_15_55 = (
    '<p class="otpoetry">"Where, O death, is your victory?'
    '<p class="otpoetry">Where, O death, is your sting?"</p>'
)


def _gen_prose(chapters, book="1corinthians"):
    """Generate for a non-poetry chapter (1corinthians is not in poetry_sections)."""
    from bible_config import get_book_by_name
    return generate_book_tex(get_book_by_name(book), chapters)


def test_inline_prose_then_otpoetry_wrapped_in_poetry_env():
    """1 Cor 15:54 pattern: prose intro + one otpoetry line →
    prose before \begin{poetry}, quote line inside, \end{poetry} after.
    """
    chapters = {15: [
        {"verse": "1", "text": '<p class="bodytext">Paul opens the chapter with a long stretch of prose. '
                       # exhaust the 5*80-char lettrine budget so later verses are out of zone
                       + 'More opening prose here. ' * 20 + '</p>'},
        {"verse": "54", "text": COR_15_54},
    ]}
    tex = _gen_prose(chapters)
    # Must contain exactly one poetry env (verse 54 block)
    assert tex.count("\\begin{poetry}") == 1
    assert tex.count("\\end{poetry}") == 1
    # The prose part must carry the verse number before the env
    assert "\\vs{54}" in tex
    idx_vs = tex.index("\\vs{54}")
    idx_begin = tex.index("\\begin{poetry}")
    assert idx_vs < idx_begin, "\\vs{54} must appear before \\begin{poetry}"
    # The quote line must be inside the env
    idx_end = tex.index("\\end{poetry}")
    body = tex[idx_begin:idx_end]
    assert "swallowed up" in body, "otpoetry line must be inside the poetry env"


def test_inline_verse_entirely_otpoetry_vs_inside_env():
    """1 Cor 15:55 — whole verse is two otpoetry lines.
    \\vs{55} must be the first token of the first poetry line (inside the env).
    """
    chapters = {15: [
        {"verse": "1", "text": '<p class="bodytext">Paul opens the chapter with a long stretch of prose. '
                       # exhaust the 5*80-char lettrine budget so later verses are out of zone
                       + 'More opening prose here. ' * 20 + '</p>'},
        {"verse": "55", "text": COR_15_55},
    ]}
    tex = _gen_prose(chapters)
    assert tex.count("\\begin{poetry}") == 1
    assert tex.count("\\end{poetry}") == 1
    idx_begin = tex.index("\\begin{poetry}")
    idx_end = tex.index("\\end{poetry}")
    body = tex[idx_begin:idx_end]
    # \vs{55} must be inside the env
    assert "\\vs{55}" in body, "\\vs{55} must be inside the poetry env"
    # Two lines: "Where, O death, is your victory?" and "Where, O death, is your sting?"
    assert "victory" in body
    assert "sting" in body
    # Second line directly follows first (no blank) for 1em indent
    lines = tex.split("\n")
    vic_idx = next(i for i, l in enumerate(lines) if "victory" in l)
    sting_idx = next(i for i, l in enumerate(lines) if "sting" in l)
    assert sting_idx == vic_idx + 1, (
        f"Second poetry line must directly follow first (couplet indent); "
        f"got {lines[vic_idx:sting_idx + 1]}"
    )


def test_inline_lettrine_zone_guard_no_poetry_env():
    """OT-poetry in lettrine zone (verse 1 or verse 2 within budget) must NOT
    produce a \\begin{poetry} env — keep flattened behavior to avoid breaking
    the drop-cap \\parshape.
    """
    chapters = {15: [
        # verse 1 is always in the lettrine zone
        {"verse": "1", "text": (
            '<p class="bodytext">Prologue prose. '
            '<p class="otpoetry">"A quote line within verse 1." </p>'
        )},
    ]}
    tex = _gen_prose(chapters)
    # No poetry env should be emitted anywhere
    assert "\\begin{poetry}" not in tex, (
        "Must NOT emit \\begin{poetry} when in lettrine zone"
    )
    # The text must still appear (flattened)
    assert "A quote line" in tex


def test_inline_noindent_before_prose_after_block():
    """When prose follows an inline poetry block in the same verse,
    the continuation prose paragraph must begin with \\noindent.
    """
    # A verse with: prose, otpoetry line, then prose (trailing bodytext)
    verse_html = (
        'Before the quote, '
        '<p class="otpoetry">"the quoted line." '
        '<p class="bodyblock">After the quote. </p>'
    )
    chapters = {15: [
        {"verse": "1", "text": '<p class="bodytext">Paul opens the chapter with a long stretch of prose. '
                       # exhaust the 5*80-char lettrine budget so later verses are out of zone
                       + 'More opening prose here. ' * 20 + '</p>'},
        {"verse": "3", "text": verse_html},
    ]}
    tex = _gen_prose(chapters)
    idx_end = tex.index("\\end{poetry}")
    after = tex[idx_end:]
    assert "\\noindent" in after.split("\n")[1], (
        "Prose continuation after \\end{poetry} must start with \\noindent"
    )


def test_inline_ann_suffix_on_last_line_of_verse():
    """ann_suffix (geneva annotation) must be appended to the last emitted
    line of the verse — inside the block if the verse ends in a poetry env,
    or on the prose line if the verse ends with prose.

    Use a fake annotations dict so we don't depend on data/ files.
    """
    chapters = {15: [
        {"verse": "1", "text": '<p class="bodytext">Paul opens the chapter with a long stretch of prose. '
                       # exhaust the 5*80-char lettrine budget so later verses are out of zone
                       + 'More opening prose here. ' * 20 + '</p>'},
        {"verse": "55", "text": COR_15_55},
    ]}
    fake_annotations = {"1corinthians": {"15": {"55": [{"letter": "a", "text": "A note."}]}}}
    from bible_config import get_book_by_name
    tex = generate_book_tex(get_book_by_name("1corinthians"), chapters,
                            annotations=fake_annotations)
    idx_begin = tex.index("\\begin{poetry}")
    idx_end = tex.index("\\end{poetry}")
    # ann_suffix must be inside the poetry env (on the last line of the block)
    body = tex[idx_begin:idx_end]
    assert "\\gva{a}" in body or "\\marginnote" in body, (
        "ann_suffix must be on the last line INSIDE the poetry env"
    )


# ---------------------------------------------------------------------------
# Minor 2 — 'pre' piece kind treated uniformly as 'flush' in ESV
# ---------------------------------------------------------------------------
def test_pre_kind_normalized_to_flush_in_esv():
    """The 'pre' piece kind (for leading text before the first sentinel) must
    be renamed to 'flush' at creation time so the emit loops handle it
    uniformly.  The 'pre' fragment is empty in all real ESV HTML (chapter-num
    strip leaves nothing before the first sentinel), but the defensive
    normalization ensures it is never silently dropped if it were non-empty.

    Test: after normalization, no piece should have kind 'pre' — verify by
    patching the sentinel-split path to produce a non-empty pre fragment,
    then assert the output contains the text (not dropped).
    """
    import esv_latex_generator as esv
    from bible_config import get_book_by_name

    # The standard PSALM_HTML: chapter-num strip removes the <b> tag,
    # begin-line-group span is stripped, so first sentinel is at pos 0.
    # No 'pre' fragment in practice — but the code must rename 'pre'->'flush'.
    html = (
        '<p class="block-indent"><span class="begin-line-group"></span>'
        '<span id="a" class="line">'
        '<b class="chapter-num" id="v1">3:1&nbsp;</b>'
        '&nbsp;&nbsp;First line text.</span>'
        '<br /><span class="end-line-group"></span></p>'
    )
    book = get_book_by_name("psalms")
    tex = "\n".join(esv._process_chapter_html(html, 3, book,
                                              is_first_chapter=False))
    # No sentinel bytes must leak
    assert "\x05" not in tex and "\x06" not in tex
    # Verse text must appear (not dropped, whether via 'flush' or 'pre' branch)
    assert "First line text" in tex
    # The source code must not use kind='pre' — it should be renamed to 'flush'
    import inspect
    src = inspect.getsource(esv._process_chapter_html)
    assert "'pre'" not in src, (
        "kind 'pre' still used in _process_chapter_html; rename to 'flush' for uniform handling"
    )


def test_inline_poetry_class_in_prose_chapter():
    """<p class="poetry"> in a chapter NOT classed as a poetry chapter
    (e.g. Zech 11:1-3 taunt poem, Deut 32 Song of Moses) must also get the
    inline \\begin{poetry} treatment, same as otpoetry."""
    zech_11_2 = ('<p class="poetry">Howl, fir tree,'
                 '<p class="poetry">for the cedar has fallen! </p>')
    chapters = {11: [
        {"verse": "1", "text": '<p class="bodytext">A long opening verse of plain prose narrative, easily exceeding any lettrine budget when repeated. '
                       # 30 repeats * 22 chars comfortably exceeds the 5*80 lettrine budget
                       + 'More prose text here. ' * 30 + '</p>'},
        {"verse": "2", "text": zech_11_2},
    ]}
    from bible_config import get_book_by_name
    tex = generate_book_tex(get_book_by_name("zechariah"), chapters)
    assert "\\begin{poetry}" in tex
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    assert "Howl, fir tree," in body
    lines = tex.split("\n")
    howl = next(i for i, l in enumerate(lines) if "Howl, fir tree," in l)
    assert "cedar has fallen!" in lines[howl + 1]   # consecutive → indent


def test_inline_lettrine_zone_verse2_flattened_and_v3_linebreak_safe():
    """Ezekiel 18 regression: verse 2 sits inside the lettrine budget zone and
    contains a poetry segment.  It must be FLATTENED (no inline env) so the
    drop-cap \\parshape survives, and verse 3's in-zone new-para line break
    (\\\\\\indent) must not follow an \\end{poetry} (vertical mode crash:
    "There's no line here to end")."""
    chapters = {18: [
        {"verse": "1", "text": '<p class="bodytext">The Lord’s message came to me: </p>'},
        {"verse": "2", "text": ('<p class="bodytext">“What do you mean by quoting this proverb:'
                                '<p class="poetry">‘The fathers eat sour grapes,'
                                '<p class="poetry">And the children’s teeth become numb?’ </p>')},
        {"verse": "3", "text": '<p class="bodytext">“As surely as I live, you will not quote this proverb anymore! </p>'},
    ]}
    from bible_config import get_book_by_name
    tex = generate_book_tex(get_book_by_name("ezekiel"), chapters)
    # Verse 2 is in-zone: no inline poetry env anywhere in this chapter
    assert "\\begin{poetry}" not in tex
    # Its poetry text still appears, flattened
    assert "sour grapes" in tex
    # Verse 3 keeps the parshape-preserving line-break form
    assert any(l.startswith("\\\\\\indent\\markboth{Ezekiel 18:3}")
               for l in tex.split("\n"))


def test_poetry_chapter_prose_verse_then_cont_verse_no_floating_vs():
    """Jeremiah 15 regression: in a POETRY chapter, verse 1 is prose
    (bodytext) and verse 2 begins with a prose lead-in (kind 'cont') followed
    by poetry lines.  The 'cont' must NOT glue \\vs{2} mid-line onto verse 1's
    justified-prose line (which makes the verse number float).  Instead \\vs{2}
    must start a fresh source line so the number hangs in the margin."""
    jer = {15: [
        {"verse": "1", "text": '<p class="bodytext">Then the Lord said to me, even if Moses and Samuel stood before me I would not feel pity. Tell them to go away! </p>'},
        {"verse": "2", "text": ("If they ask you, 'Where should we go?' tell them the Lord says this:"
                                 '<p class="poetry">Those destined to die of disease, to death by disease.'
                                 '<p class="poetry">Those destined for war, to death in war. </p>')},
    ]}
    from bible_config import get_book_by_name
    tex = generate_book_tex(get_book_by_name("jeremiah"), jer)
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    src = body.split("\n")
    # \vs{2} must begin a source line, not be glued mid-line onto another.
    vs2 = [l for l in src if "\\vs{2}" in l]
    assert vs2, "\\vs{2} missing"
    assert all(l.lstrip().startswith("\\vs{2}") for l in vs2), (
        f"\\vs{{2}} is glued mid-line (floats): {vs2}")
    # The chapter-opener line (verse 1) must NOT contain \vs{2}
    ch_line = next(l for l in src if "\\ch{15}" in l)
    assert "\\vs{2}" not in ch_line, "verse 2 glued onto the \\ch prose line"


def test_poetry_true_continuation_still_glues_midline():
    """A genuine continuation — previous verse ENDS on a poetry line and the
    next verse begins with bare 'cont' text — must still glue mid-line (that is
    the correct ragged-poetry behavior; only prose-glue floats)."""
    chapters = {5: [
        {"verse": "1", "text": '<p class="poetry">An open poetic line that does not close, </p>'},
        {"verse": "2", "text": 'continuing the same poetic line here. </p>'},
    ]}
    from bible_config import get_book_by_name
    tex = generate_book_tex(get_book_by_name("amos"), chapters)
    body = tex.split("\\begin{poetry}")[1].split("\\end{poetry}")[0]
    src = body.split("\n")
    # verse 2 must NOT begin its own source line — it continues verse 1's line.
    assert not any(l.lstrip().startswith("\\vs{2}") for l in src), (
        f"true continuation should glue mid-line: {src}")
    assert "\\vs{2}" in body
