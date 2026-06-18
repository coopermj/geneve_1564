"""Convert fetched NET Bible verse data to LaTeX using the scripture package."""

import json
import os
import re

from bible_config import BookInfo, BOOKS


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_POETRY_PATH = os.path.join(_SCRIPT_DIR, "poetry_sections.json")
_ARGUMENTS_PATH = os.path.join(_PROJECT_ROOT, "data", "geneva_arguments.json")
_RED_LETTER_PATH = os.path.join(_PROJECT_ROOT, "data", "red_letter_verses.json")

_poetry_config: dict | None = None
_red_letter_verses: dict | None = None


def _load_red_letter_verses() -> dict:
    global _red_letter_verses
    if _red_letter_verses is None:
        if os.path.isfile(_RED_LETTER_PATH):
            with open(_RED_LETTER_PATH, encoding="utf-8") as f:
                _red_letter_verses = json.load(f)
        else:
            _red_letter_verses = {}
    return _red_letter_verses


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
            out.append("\\redletteroff{}")
        # A non-Jesus verse is a safe resync point: clear all quote state so a
        # stray unclosed quote in earlier text cannot leak depth into later verses.
        state.in_jesus = False
        state.open_depth = None
        state.depth = 0
        out.append(text)
        return "".join(out)

    if state.in_jesus or desc.get("starts_in_jesus"):
        if not state.in_jesus:
            state.in_jesus = True
            state.open_depth = 0
        out.append("\\redletteron{}")

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
                        out.append("\\redletteron{}")
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
                out.append("\\redletteroff{}")
                state.in_jesus = False
                state.open_depth = None
            continue
        out.append(text[i])
        i += 1

    if state.in_jesus:
        out.append("\\redletteroff{}")
        state.in_jesus = False
        state.open_depth = None
    return "".join(out)


def _load_poetry_config() -> dict:
    global _poetry_config
    if _poetry_config is None:
        with open(_POETRY_PATH, "r", encoding="utf-8") as f:
            _poetry_config = json.load(f)
    return _poetry_config


def _is_poetry_chapter(book_dir: str, chapter: int) -> bool:
    """Check if a given chapter should be rendered as poetry."""
    config = _load_poetry_config()
    entry = config.get(book_dir)
    if entry is None:
        return False
    if entry.get("full_book"):
        return True
    for start, end in entry.get("chapters", []):
        if start <= chapter <= end:
            return True
    return False


_arguments_cache: dict | None = None


def _load_argument(book_dir: str) -> str | None:
    global _arguments_cache
    if _arguments_cache is None:
        if os.path.isfile(_ARGUMENTS_PATH):
            with open(_ARGUMENTS_PATH, "r", encoding="utf-8") as f:
                _arguments_cache = json.load(f)
        else:
            _arguments_cache = {}
    text = _arguments_cache.get(book_dir, "")
    return text if text else None


# LaTeX special characters that need escaping
_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape_latex(text: str) -> str:
    r"""Escape LaTeX special characters in raw source prose.

    IMPORTANT: this must be called on bare text BEFORE any LaTeX commands
    (\textsc, \lettrine, \vs, ...) are injected. Escaping happens per
    character, so it also escapes literal ``\``, ``{`` and ``}`` in the
    source -- which is only safe while no genuine commands are present.
    """
    return "".join(_LATEX_SPECIAL.get(ch, ch) for ch in text)


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


def _strip_html_tags(html: str) -> str:
    """Strip HTML tags from API response, converting notes to footnotes.

    The API returns:
    - <st data-num="XXXX" class="">word</st>  -> just keep the word
    - <n id="N" />  -> translator note markers (we skip these for now)
    - <p class="bodytext">...</p>  -> paragraph wrappers
    - Smart quotes: \u201c \u201d \u2018 \u2019
    """
    text = html

    # Replace <p> tags with a space to prevent adjacent words merging
    text = re.sub(r'</?p[^>]*>', ' ', text)

    # Remove <st> tags but keep content
    text = re.sub(r'<st[^>]*>', '', text)
    text = re.sub(r'</st>', '', text)

    # Remove note markers <n id="N" /> — these are note reference numbers
    # We strip them since the NET Bible notes aren't included in the free API
    text = re.sub(r'<n\s+id="[^"]*"\s*/>', '', text)

    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Convert HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&quot;", '"')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def _convert_smart_quotes(text: str) -> str:
    """Convert Unicode smart quotes to LaTeX curly quote commands."""
    text = text.replace("\u201c", "``")   # left double quote
    text = text.replace("\u201d", "''")   # right double quote
    text = text.replace("\u2018", "`")    # left single quote
    text = text.replace("\u2019", "'")    # right single quote
    text = text.replace("\u2014", "---")  # em dash
    text = text.replace("\u2013", "--")   # en dash
    return text


def _apply_divine_names(text: str) -> str:
    r"""Replace LORD/GOD with \textsc{Lord}/\textsc{God} for divine name styling."""
    # Match standalone LORD (all caps) — the tetragrammaton convention
    text = re.sub(r'\bLORD\b', r'\\textsc{Lord}', text)
    text = re.sub(r'\bGOD\b', r'\\textsc{God}', text)
    return text


# Map English book directory names to their heading image filenames (without extension).
# Only books that have a heading image in images/ are listed here.
_HEADING_IMAGES = {
    "genesis": "images/genese_heading",
}


def _chapter_table(book_dir: str, chapter_nums: list[int]) -> str:
    """Return a compact chapter navigation row for the book heading page.

    Renders as a centred, single-line row of chapter numbers (italic, small)
    separated by thin spaces, each a PDF hyperlink to its chapter target
    (ch-{book_dir}-{N}).  Intended for use as the 6th argument to \\bbook.
    """
    links = [
        f"\\hyperlink{{ch-{book_dir}-{n}}}{{\\textit{{\\small {n}}}}}"
        for n in chapter_nums
    ]
    inner = "\\hspace{0.4em}".join(links)
    return (
        "\\vspace{4pt}%\n"
        "\\parbox[t]{\\linewidth}{\\centering\\small" + inner + "}%\n"
        "\\vspace{6pt}"
    )


def _find_heading_image(book_dir: str) -> str | None:
    """Return the LaTeX-relative image path if a heading image exists, else None."""
    # Check explicit mapping first
    if book_dir in _HEADING_IMAGES:
        img_path = _HEADING_IMAGES[book_dir]
        # Verify the file actually exists (with .pdf extension)
        full_path = os.path.join(_PROJECT_ROOT, img_path + ".pdf")
        if os.path.isfile(full_path):
            return img_path
    # Also check for images/<book_dir>_heading.pdf as a convention
    convention_path = f"images/{book_dir}_heading"
    full_path = os.path.join(_PROJECT_ROOT, convention_path + ".pdf")
    if os.path.isfile(full_path):
        return convention_path
    return None


def _make_lettrine(text: str, lettrine_lines: int | None = None,
                   color: str | None = None) -> str:
    r"""Wrap the first letter of text in \lettrine{}{} with small-capped rest of word.

    The second mandatory argument of \lettrine gets the rest of the initial word
    in \textsc{}, and the color is applied to the drop cap letter.

    E.g. "In the beginning" -> \lettrine{\color{pentateuch}I}{\textsc{n}} the beginning
         ``Let there be"    -> ``\lettrine{\color{gospels}L}{\textsc{et}} there be

    Args:
        text: The verse text to process.
        lettrine_lines: Override the number of lines for the drop cap.
        color: LaTeX color name for the drop cap letter.
    """
    # Strip leading whitespace
    text = text.lstrip()

    prefix = ""
    # Strip all leading LaTeX opening quotes (`` and/or `) and open parens.
    # Also strip NET cross-reference labels like (5:27) that some chapters open with.
    # Handles nested quotes like ``\`You... (double-then-single)
    while True:
        if text.startswith("``"):
            prefix += "``"
            text = text[2:]
        elif text.startswith("`"):
            prefix += "`"
            text = text[1:]
        elif m := re.match(r'\(\d+:\d+[a-z]?\)\s*', text):
            # Cross-reference label like (5:27) or (63:19b) — keep as prefix
            prefix += m.group(0)
            text = text[m.end():]
        elif text.startswith("("):
            prefix += "("
            text = text[1:]
        else:
            break

    # Skip any leading whitespace after quotes/prefixes
    text = text.lstrip()

    if not text:
        return prefix + text

    # Extract first letter
    first_letter = text[0]
    after_first = text[1:]

    # Extract the rest of the first word (letters up to first space/punctuation)
    match = re.match(r'([A-Za-z]*)(.*)', after_first, re.DOTALL)
    if match:
        rest_of_word = match.group(1)
        remainder = match.group(2)
    else:
        rest_of_word = ""
        remainder = after_first

    # Build lettrine options
    opts = f"[lines={lettrine_lines}]" if lettrine_lines else ""

    # Build first arg with optional color
    if color:
        first_arg = f"\\color{{{color}}}{first_letter}"
    else:
        first_arg = first_letter

    # Build second arg with small caps for rest of word
    if rest_of_word:
        second_arg = f"\\textsc{{{rest_of_word}}}"
    else:
        second_arg = ""

    return f"{prefix}\\lettrine{opts}{{{first_arg}}}{{{second_arg}}}{remainder}"


_HEBREW_RE = re.compile(r"[֐-׿]+\s*")


def _style_poetry_segment(kind: str, text: str) -> str:
    if kind == "lamhebrew":
        text = _HEBREW_RE.sub("", text).strip()
        # Use \textit{} (not {\itshape}) so the line does NOT start with a
        # bare ``{`` — the scripture poetry obeylines handler fails on lines
        # that begin with a begin-group token.
        return f"\\textit{{{text}}}"
    if kind == "psasuper":
        return f"\\textit{{{text}}}"
    if kind == "sosspeaker":
        return f"\\textbf{{\\textit{{{text}}}}}"
    return text


def _emit_poetry_verse(out: list, kinds: list, texts: list,
                       verse_num: int, mark: str, ann_suffix: str,
                       ch_open, prev_in_poetry_line: bool = False) -> bool:
    """Append the poetic lines of one verse to *out*; return open-line state.

    Layout (ESV-style two-level): a segment that STARTS a unit — the verse's
    first segment, any prose interlude, or the first line after a label or
    stanza break — is emitted flush (preceded by a blank line, which resets
    the obeylines indent).  A "line" segment directly following another
    poetry line goes on the very next source line with NO blank between, so
    the scripture poetry environment gives it the 1em second-half indent.

    ch_open: when set (verse 1), the FIRST segment goes on the ``\\ch{N} ...``
    source line.  If that segment is itself a poetry line, the next line
    follows consecutively (couplet indent, mirroring the ESV no-title
    chapter start); if it is a superscription, the first poetry line below
    starts flush.

    prev_in_poetry_line: True when the PREVIOUS verse ended mid-poetic-line,
    so a leading "cont" segment here is a genuine continuation and may glue
    onto that ragged poetic line.  When False (e.g. the previous verse was
    prose — a bodytext verse inside a poetry chapter, as in Jeremiah 15:1),
    a leading "cont" must NOT glue: gluing ``\\vs{N}`` into justified prose
    makes the verse number float (the inter-word space stretches).  Instead
    it starts a fresh flush source line so the number hangs in the margin.
    Returns whether this verse ended mid-poetic-line, for the next verse.

    IMPORTANT: decorated segments (psasuper, sosspeaker, lamhebrew) start
    with ``{...}`` and MUST NOT appear as the first token of a new blank-line-
    separated paragraph in the obeylines poetry environment — the scripture
    package's peek_analysis_map fails with a bare ``{``.  Such segments are
    queued and prepended inline to the next "line" segment.
    """
    first_emitted = False
    pending = ""         # decorated segments queued for next "line"
    prev_line = prev_in_poetry_line  # carries open-poetic-line state across verses

    for kind, text in zip(kinds, texts):
        text = text.strip()
        if not text:
            continue

        # Apply styling
        styled = _style_poetry_segment(kind, text)

        # Decorated kinds (psasuper, sosspeaker, lamhebrew) start with ``{``
        # and MUST NOT open a new blank-line-separated source paragraph on
        # their own — the scripture obeylines handler crashes on a bare ``{``
        # at line start.  For verse 1 they are safe on the ``\ch{N}`` line
        # (which starts with a control sequence); for all other contexts they
        # are queued and prepended to the next "line" segment.
        is_decorated = kind in ("psasuper", "sosspeaker", "lamhebrew")
        if is_decorated and ch_open is None:
            pending += styled + " "
            prev_line = False  # a label starts a new unit → next line flush
            continue

        # --- First content segment of this verse ---
        if not first_emitted:
            first_emitted = True
            if ch_open is not None:
                # Verse 1: this segment (decorated or not) goes on the \ch line.
                out.append(f"{ch_open}{styled}")
                ch_open = None  # consumed; subsequent segments go on own lines
                prev_line = (kind == "line")
            elif kind == "cont" and prev_line:
                # Genuine continuation of an open (ragged) poetic line: glue
                # mid-line.  Safe because poetry lines are not justified.
                out[-1] += f" \\vs{{{verse_num}}}{mark}{pending}{styled}"
                pending = ""
                prev_line = True
            elif kind == "cont":
                # Lead-in after a PROSE verse (or chapter opener): gluing
                # \vs{N} into justified prose floats the number.  Start a
                # fresh flush source line so the number hangs in the margin.
                out.append("")
                out.append(f"\\vs{{{verse_num}}}{mark}{pending}{styled}")
                pending = ""
                prev_line = False
            elif kind == "break":
                # A verse that starts with a stanza break (unusual but possible)
                out.append("\\extraskip")
                out.append("")
                out.append(f"\\vs{{{verse_num}}}{mark}{pending}{styled}")
                pending = ""
                prev_line = True
            else:
                out.append("")
                out.append(f"\\vs{{{verse_num}}}{mark}{pending}{styled}")
                pending = ""
                prev_line = (kind == "line")
            continue

        # --- Subsequent segments (including verse 1's 2nd+ segments) ---
        if kind == "break":
            out.append("\\extraskip")
            out.append("")
            out.append(f"{pending}{styled}")
            pending = ""
            prev_line = True
        elif kind == "line" and prev_line and not pending:
            # line directly after line → consecutive source line → 1em indent
            out.append(styled)
        else:
            out.append("")
            out.append(f"{pending}{styled}")
            pending = ""
            prev_line = (kind == "line")

    # Flush any trailing decorated segments (e.g. sosspeaker at end of verse)
    if pending.strip() and first_emitted:
        out[-1] += f" {pending.strip()}"

    # Handle the case where ALL segments were decorated kinds (psasuper,
    # sosspeaker, lamhebrew) and ch_open was None — every segment went into
    # ``pending`` but ``first_emitted`` never became True, so the verse text
    # was silently dropped.  Emit as its own flush source line with \vs{N}.
    if pending.strip() and not first_emitted:
        first_emitted = True
        out.append("")
        out.append(f"\\vs{{{verse_num}}}{mark}{pending.strip()}")

    if first_emitted and ann_suffix:
        # Guard: never append ann_suffix to a bare \extraskip line.
        # If the last emitted line is \extraskip (verse ended on a stanza
        # break — unusual but latently possible), walk back to the last
        # non-extraskip line and append the suffix there.
        target = len(out) - 1
        while target >= 0 and out[target] == "\\extraskip":
            target -= 1
        if target >= 0:
            out[target] += ann_suffix
        else:
            out.append(ann_suffix)

    return prev_line


def _starts_paragraph(raw_html: str) -> bool:
    """Check if this verse starts a new paragraph (has a <p> tag)."""
    return bool(re.search(r'<p\b[^>]*>', raw_html))


def _has_inline_otpoetry(raw_html: str) -> bool:
    """Return True if the verse contains poetic-line segments.

    Used to decide whether to emit an inline \\begin{poetry}...\\end{poetry}
    block inside a prose chapter verse (when outside the lettrine zone).
    Matches both <p class="otpoetry"> (OT quotes in the NT) and
    <p class="poetry"> (poetic passages in chapters not classed as poetry
    chapters, e.g. Deut 32, Isa 16/18, Jer 12, Zech 11).
    """
    return bool(re.search(r'<p class="(?:ot)?poetry">', raw_html))


def _emit_inline_poetry_verse(
    out: list[str],
    kinds: list[str],
    texts: list[str],
    verse_num: int,
    mark: str,
    ann_suffix: str,
    new_para: bool,
) -> None:
    r"""Emit a prose-chapter verse that contains inline poetry-line blocks.

    Layout rules:
    - Runs of consecutive "line" segments are wrapped in
      \\begin{poetry}...\\end{poetry}.
    - Within a run: first line of the run is flush (no blank before it inside
      the env — it goes directly after \\begin{poetry}).  Subsequent lines
      follow directly (no blank), giving the 1em scripture indent.
    - If the verse STARTS with a line run (no leading prose): \\vs{N} + mark
      are prepended to the first poetry line inside the env.
    - If there is leading prose: \\vs{N} + mark + prose text go on the prose
      line(s) before \\begin{poetry}.
    - Prose that follows a poetry block gets \\noindent so it is not
      paragraph-indented.
    - ann_suffix is appended to the last emitted text line of the verse
      (inside the env if the verse ends with a poetry block).
    - new_para handling (\\everypar{}  blank  \\parshape=0) applies when
      new_para is True and the verse has leading prose.
    """
    # Partition kinds/texts into groups: contiguous runs of "line" are one
    # "block" group; everything else is a "prose" group.
    # Each group: ("line_run", [texts]) or ("prose", [texts])
    groups: list[tuple[str, list[str]]] = []
    i = 0
    n = len(kinds)
    while i < n:
        if kinds[i] == "line":
            run = []
            while i < n and kinds[i] == "line":
                run.append(texts[i])
                i += 1
            groups.append(("line_run", run))
        else:
            # prose-like segment (bodytext, bodyblock, quote, etc.)
            groups.append(("prose", [texts[i]]))
            i += 1

    emitted_vs = False  # True once \vs{N} has been emitted

    for g_idx, (gtype, gtexts) in enumerate(groups):
        is_last_group = (g_idx == len(groups) - 1)
        # ann_suffix goes on the last text line of the last group
        group_suffix = ann_suffix if is_last_group else ""

        if gtype == "prose":
            prose_text = " ".join(t.strip() for t in gtexts if t.strip())
            if not prose_text:
                continue
            if not emitted_vs:
                # First prose group carries the verse marker
                if new_para:
                    out.append("\\everypar{}")
                    out.append("")
                    out.append("\\parshape=0")
                out.append(f"{mark}\\vs{{{verse_num}}}{prose_text}{group_suffix}")
                emitted_vs = True
            else:
                # Prose after a poetry block: must not be paragraph-indented
                out.append(f"\\noindent {prose_text}{group_suffix}")
        else:
            # line_run → \begin{poetry} ... \end{poetry}
            if new_para and not emitted_vs:
                # Paragraph break applies before this group (starts with poetry)
                out.append("\\everypar{}")
                out.append("")
                out.append("\\parshape=0")
            out.append("\\begin{poetry}")
            # Find the last non-empty line index for suffix placement
            last_nonempty = max(
                (i for i, t in enumerate(gtexts) if t.strip()), default=-1)
            for l_idx, line_text in enumerate(gtexts):
                line_text = line_text.strip()
                if not line_text:
                    continue
                if l_idx == 0 and not emitted_vs:
                    # \vs{N} goes as first token of the first line inside the env
                    line_out = f"\\vs{{{verse_num}}}{mark}{line_text}"
                    emitted_vs = True
                else:
                    line_out = line_text
                if is_last_group and l_idx == last_nonempty:
                    line_out += group_suffix
                out.append(line_out)
            if is_last_group and group_suffix and last_nonempty == -1:
                # Defensive: an all-empty run never hits the suffix branch
                # above — don't silently drop the annotation suffix.
                out[-1] += group_suffix
            out.append("\\end{poetry}")


def _process_verse_text(raw_html: str) -> str:
    """Full pipeline: strip HTML, escape, convert quotes, apply divine names.

    Escaping runs on the bare prose BEFORE smart-quote and divine-name
    commands are injected, so literal ``{``, ``}`` and ``\\`` in the source
    are escaped without corrupting the injected ``\\textsc{}`` commands.
    """
    text = _strip_html_tags(raw_html)
    text = _escape_latex(text)
    text = _convert_smart_quotes(text)
    text = _apply_divine_names(text)
    return text


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
        corrections: Optional {manifest_idx: float | "footnote"}.

    Returns:
        LaTeX string to append after the verse text.
    """
    if not verse_annotations:
        return ""

    parts = []
    for ann in verse_annotations:
        idx = counter[0]
        counter[0] += 1
        # Store first 20 chars of plain text for content-based PDF matching
        _plain = ann["text"][:20].replace("\n", " ").strip()
        manifest.append({"idx": idx, "book": book_dir, "ch": ch_num,
                          "verse": verse_num, "letter": ann["letter"],
                          "text_prefix": _plain})

        letter = ann["letter"]
        text = _escape_latex(_convert_smart_quotes(ann["text"]))
        inline = f"\\gva{{{letter}}}"
        note_content = f"\\gva{{{letter}}}\\,{text}"

        correction = corrections.get(idx, 0) if corrections else 0
        if correction == "footnote":
            # Use the annotation letter as the footnote mark (matching the
            # margin-note \gva scheme). With ~11k footnotes, the default
            # continuous numbering produces 4-5 digit superscripts inline.
            # \thefootnote is redefined group-locally, so the letter appears
            # as the mark both inline and at the column bottom; the \gva
            # prefixes become redundant and are dropped.
            parts.append(
                f"{{\\renewcommand{{\\thefootnote}}{{\\textit{{{letter}}}}}"
                f"\\footnote{{{text}}}}}"
            )
        else:
            parts.append(f"{inline}\\marginnote{{{note_content}}}")

    return "".join(parts)


def generate_book_tex(
    book: BookInfo,
    chapters_data: dict[int, list[dict]],
    plan_endpoints: dict | None = None,
    annotations: dict | None = None,
    corrections: dict | None = None,
    note_manifest: list | None = None,
) -> str:
    """Generate the complete .tex content for a book.

    Args:
        book: BookInfo with name, directory, group, long_title, subtitle, etc.
        chapters_data: {chapter_num: [verse_dicts]} from the fetcher
        plan_endpoints: Optional {(book_dir, end_ch): [anchor_id, ...]} for
            return-to-plan octagon markers.
        annotations: Optional pre-loaded annotations dict. If None, loads from
            data/geneva_annotations.json automatically.
        corrections: Optional {manifest_idx: float | "footnote"} for marginnote
            offset corrections or footnote fallback.
        note_manifest: Optional list to append note records to for tracking.
    """
    lines = []

    # Load annotations for this book
    if annotations is None:
        _book_annotations = _load_annotations().get(book.directory, {})
    else:
        _book_annotations = annotations.get(book.directory, {})

    # Shared mutable counter and manifest for note tracking
    _manifest = note_manifest if note_manifest is not None else []
    _counter = [len(_manifest)]
    lines.append(f"% {book.name} — Generated by generate_bible.py")
    lines.append(f"% NET Bible text, scripture package formatting")

    heading_img = _find_heading_image(book.directory)
    escaped_title = _escape_latex(book.long_title)
    escaped_sub = _escape_latex(book.subtitle)
    argument = _escape_latex(_load_argument(book.directory) or "")
    sorted_chapters = sorted(chapters_data.keys())
    ch_table = _chapter_table(book.directory, sorted_chapters)
    lines.append(f"\\gdef\\bbookchaptable{{{ch_table}}}")
    if heading_img:
        lines.append(f"\\bbook[{heading_img}]{{{escaped_title}}}{{{escaped_sub}}}{{{argument}}}{{{book.directory}}}")
    else:
        lines.append(f"\\bbook{{{escaped_title}}}{{{escaped_sub}}}{{{argument}}}{{{book.directory}}}")

    # PDF outline: top-level bookmark for the book (points to the \bbook anchor)
    lines.append(f"\\bookmark[dest={{book-{book.directory}}},level=0]{{{book.name}}}")
    lines.append("")
    lines.append("\\begin{scripture}")

    for ch_num in sorted_chapters:
        verses = chapters_data[ch_num]
        is_poetry = _is_poetry_chapter(book.directory, ch_num)

        lines.append("")

        if is_poetry:
            lines.append("\\begin{poetry}")

        # Character budget: while positive, paragraph breaks within the
        # lettrine zone use \\ (preserving \parshape) instead of \par
        # which would reset the shape and let text overlap the drop cap.
        lettrine_char_budget = 0
        rl_state = _RLState()
        poetry_open_line = False  # did the previous poetry verse end mid-line?

        for verse in verses:
            verse_num = int(verse["verse"])
            raw_html = verse["text"]
            new_para = _starts_paragraph(raw_html)
            text = _process_verse_text(raw_html)
            desc = _get_red_letter_desc(book.directory, ch_num, verse_num)

            ch_annotations = _book_annotations.get(str(ch_num), {})
            verse_anns = ch_annotations.get(str(verse_num), [])
            ann_suffix = _build_annotation_suffix(
                book.directory, ch_num, verse_num, verse_anns,
                _counter, _manifest, corrections
            )

            if is_poetry:
                segs = _split_poetry_segments(raw_html)
                seg_texts = [_process_verse_text(h) for _, h in segs]
                joined = _render_red_letter("\x05".join(seg_texts), desc, rl_state)
                seg_texts = joined.split("\x05")
                kinds = [k for k, _ in segs]
                mark = (f"\\markboth{{{book.name} {ch_num}:{verse_num}}}"
                        f"{{{book.name} {ch_num}:{verse_num}}}")
                ch_open = None
                if verse_num == 1:
                    lines.append(f"\\markboth{{{book.name} {ch_num}:1}}"
                                 f"{{{book.name} {ch_num}:1}}")
                    if ch_num > 1:
                        lines.append("\\Needspace*{8\\baselineskip}")
                    lines.append(f"\\bookmark[dest={{ch-{book.directory}-{ch_num}}},"
                                 f"level=1]{{{book.name} {ch_num}}}")
                    ch_open = (f"\\ch{{{ch_num}}} \\allowchapbreak"
                               f"\\hypertarget{{ch-{book.directory}-{ch_num}}}{{}}")
                poetry_open_line = _emit_poetry_verse(
                    lines, kinds, seg_texts, verse_num, mark,
                    ann_suffix, ch_open, poetry_open_line)
            elif verse_num == 1:
                # Chapter start — use \ch{N} with lettrine drop cap.
                if ch_num == 1:
                    lettrine_text = _make_lettrine(
                        text, lettrine_lines=8, color=book.group)
                    lettrine_char_budget = 8 * 80
                else:
                    lettrine_text = _make_lettrine(text, lettrine_lines=5, color=book.group)
                    lettrine_char_budget = 5 * 80
                lettrine_char_budget -= len(text)
                lettrine_text = _render_red_letter(lettrine_text, desc, rl_state)
                lines.append(f"\\markboth{{{book.name} {ch_num}:1}}{{{book.name} {ch_num}:1}}")
                # Ensure enough vertical space for the chapter heading +
                # lettrine before starting.  Without this, the scripture
                # package's \nobreak glues heading to verse 1, and when the
                # lettrine is too tall for the remaining column TeX pushes
                # the whole block out, leaving large blank gaps.
                if ch_num > 1:
                    lines.append("\\Needspace*{8\\baselineskip}")
                lines.append(f"\\bookmark[dest={{ch-{book.directory}-{ch_num}}},level=1]{{{book.name} {ch_num}}}")
                lines.append(f"\\ch{{{ch_num}}} \\allowchapbreak\\hypertarget{{ch-{book.directory}-{ch_num}}}{{}}{lettrine_text}{ann_suffix}\\everypar{{}}")
            else:
                mark = f"\\markboth{{{book.name} {ch_num}:{verse_num}}}{{{book.name} {ch_num}:{verse_num}}}"
                lettrine_char_budget -= len(text)
                # Inline OT-poetry blocks in prose chapters: wrap consecutive
                # otpoetry segments in \begin{poetry}...\end{poetry}.
                # Lettrine zone guard: a verse still inside the drop-cap
                # budget (e.g. Ezekiel 18:2's proverb) must be FLATTENED —
                # an inner env there destroys the lettrine \parshape, and a
                # following in-zone verse's \\ line break then crashes in
                # vertical mode ("There's no line here to end").
                if _has_inline_otpoetry(raw_html) and lettrine_char_budget <= 0:
                    segs = _split_poetry_segments(raw_html)
                    seg_texts = [_process_verse_text(h) for _, h in segs]
                    joined = _render_red_letter("\x05".join(seg_texts), desc, rl_state)
                    seg_texts = joined.split("\x05")
                    kinds = [k for k, _ in segs]
                    _emit_inline_poetry_verse(lines, kinds, seg_texts,
                                             verse_num, mark, ann_suffix,
                                             new_para)
                else:
                    text = _render_red_letter(text, desc, rl_state)
                    if new_para:
                        if lettrine_char_budget > 0:
                            # Within lettrine zone: line break (not \par) to
                            # preserve \parshape and avoid drop-cap overlap.
                            lines.append(f"\\\\\\indent{mark}\\vs{{{verse_num}}}{text}{ann_suffix}")
                        else:
                            lines.append("\\everypar{}")
                            lines.append("")
                            lines.append("\\parshape=0")
                            lines.append(f"{mark}\\vs{{{verse_num}}}{text}{ann_suffix}")
                    else:
                        lines.append(f"{mark}\\vs{{{verse_num}}}{text}{ann_suffix}")

        # Return-to-plan octagon after last verse of endpoint chapters
        if plan_endpoints and (book.directory, ch_num) in plan_endpoints:
            for anchor_id in plan_endpoints[(book.directory, ch_num)]:
                lines[-1] += f"\\rpreturn{{{anchor_id}}}"

        if is_poetry:
            lines.append("\\end{poetry}")

    lines.append("")
    lines.append("\\end{scripture}")
    lines.append("")

    return "\n".join(lines)


def generate_testament_tex(books: list, testament_label: str,
                           subdir: str = "livres") -> str:
    """Generate old_testament.tex or new_testament.tex with \\input lines."""
    lines = []
    lines.append(f"% {testament_label} — Generated by generate_bible.py")
    for book in books:
        lines.append(f"\\input{{{subdir}/{book.directory}/{book.directory}}}")
    lines.append("")
    return "\n".join(lines)


# Book group display names and order for the color index
_GROUP_INFO = [
    ("pentateuch", "The Pentateuch"),
    ("historical", "Historical Books"),
    ("wisdom", "Wisdom \\& Poetry"),
    ("majorprophets", "Major Prophets"),
    ("minorprophets", "Minor Prophets"),
    ("gospels", "The Gospels"),
    ("acts", "Acts"),
    ("pauline", "Pauline Epistles"),
    ("general", "General Epistles"),
    ("revelation", "Revelation"),
]

# After these groups, force a column break. Breaking after "acts" (rather than
# "minorprophets") balances the three columns: putting Gospels+Acts in column 2
# keeps column 3 (Pauline+General+Revelation) short enough to fit one page even
# at the 13pt net_bible body size.
_COLUMN_BREAK_AFTER = {"wisdom", "acts"}


def generate_color_index_tex() -> str:
    """Generate a 3-column color index page grouping books by category.

    Layout: col 1 = Pentateuch + Historical + Wisdom,
            col 2 = Major Prophets + Minor Prophets + Gospels + Acts,
            col 3 = Pauline + General Epistles + Revelation.
    Sections are never split across columns.
    """
    lines = []
    lines.append("% Color Index — Generated by generate_bible.py")
    # \onecolumn forces \clearpage and switches to single-column mode so that
    # the multicols{3} environment spans the full text width.
    lines.append("\\onecolumn")
    lines.append("\\thispagestyle{empty}")
    lines.append("\\hypertarget{toc}{}")
    lines.append("\\vspace*{20pt}")
    lines.append("{\\centering\\huge\\booktitlefont\\scshape Index of Books"
                 "\\\\\\char\"2766\\par}")
    lines.append("\\vspace{10pt}")
    lines.append("\\begin{multicols}{3}")
    lines.append("\\small")
    lines.append("\\setlength{\\parskip}{0pt}")
    lines.append("\\setlength{\\parindent}{0pt}")
    lines.append("")

    # Build a lookup: group -> list of BookInfo
    group_books: dict[str, list[BookInfo]] = {}
    for book in BOOKS:
        group_books.setdefault(book.group, []).append(book)

    for group_key, group_label in _GROUP_INFO:
        books = group_books.get(group_key, [])
        if not books:
            continue
        lines.append(f"\\noindent{{\\allurafont\\large\\color{{{group_key}}}{group_label}}}\\\\")
        for book in books:
            lines.append(f"\\hspace{{1em}}\\hyperlink{{book-{book.directory}}}{{{book.name}}}\\\\")
        lines.append("\\vspace{4pt}")
        lines.append("")
        if group_key in _COLUMN_BREAK_AFTER:
            lines.append("\\columnbreak")
            lines.append("")

    lines.append("\\end{multicols}")
    # Restore two-column layout for the rest of the document.
    lines.append("\\twocolumn")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reverse abbreviation map for reading plan display labels
# ---------------------------------------------------------------------------
_DIR_TO_ABBREV = {
    "genesis": "Gen", "exodus": "Ex", "leviticus": "Lev", "numbers": "Num",
    "deuteronomy": "Deut", "joshua": "Josh", "judges": "Judg", "ruth": "Ruth",
    "1samuel": "1 Sam", "2samuel": "2 Sam", "1kings": "1 Ki", "2kings": "2 Ki",
    "1chronicles": "1 Chr", "2chronicles": "2 Chr", "ezra": "Ezra",
    "nehemiah": "Neh", "esther": "Est", "job": "Job", "psalms": "Ps",
    "proverbs": "Prov", "ecclesiastes": "Eccl", "songofsolomon": "Song",
    "isaiah": "Is", "jeremiah": "Jer", "lamentations": "Lam",
    "ezekiel": "Eze", "daniel": "Dan", "hosea": "Hos", "joel": "Joel",
    "amos": "Amos", "obadiah": "Obad", "jonah": "Jonah", "micah": "Mic",
    "nahum": "Nah", "habakkuk": "Habak", "zephaniah": "Zeph",
    "haggai": "Hag", "zechariah": "Zech", "malachi": "Mal",
    "matthew": "Matt", "mark": "Mark", "luke": "Luke", "john": "John",
    "acts": "Acts", "romans": "Rom", "1corinthians": "1 Cor",
    "2corinthians": "2 Cor", "galatians": "Gal", "ephesians": "Eph",
    "philippians": "Phil", "colossians": "Col",
    "1thessalonians": "1 Thess", "2thessalonians": "2 Thess",
    "1timothy": "1 Tim", "2timothy": "2 Tim", "titus": "Tit",
    "philemon": "Philm", "hebrews": "Heb", "james": "James",
    "1peter": "1 Pet", "2peter": "2 Pet", "1john": "1 John",
    "2john": "2 John", "3john": "3 John", "jude": "Jude",
    "revelation": "Rev",
}


def _segment_display(seg: dict) -> str:
    """Build a display label like 'Gen 1--3' for one segment."""
    abbrev = _DIR_TO_ABBREV.get(seg["book_dir"], seg["book_dir"])
    start, end = seg["start_ch"], seg["end_ch"]
    if start == end:
        return f"{abbrev} {start}"
    return f"{abbrev} {start}--{end}"


def _entry_hyperlinks(entry: dict) -> str:
    r"""Build LaTeX hyperlinked passage reference(s) for a reading-plan entry.

    Single segment:  \hyperlink{ch-genesis-1}{Gen 1--3}
    Combined ('/'):  \hyperlink{ch-matthew-28}{Matt 28} / \hyperlink{ch-mark-16}{Mark 16}
    Multi-book ('-'): \hyperlink{ch-2john-1}{2 John--3 John}
    """
    raw = entry["raw"]
    segments = entry["segments"]

    if "/" in raw:
        # Combined: each '/' part is a separate hyperlink
        parts = []
        for seg in segments:
            target = f"ch-{seg['book_dir']}-{seg['start_ch']}"
            display = _segment_display(seg)
            parts.append(f"\\hyperlink{{{target}}}{{{display}}}")
        return " / ".join(parts)

    # Single or multi-book range: one hyperlink covering all segments
    if len(segments) == 1:
        display = _segment_display(segments[0])
    else:
        # Multi-book range like "2 John-3 John"
        display = raw.replace("-", "--")
    target = f"ch-{segments[0]['book_dir']}-{segments[0]['start_ch']}"
    return f"\\hyperlink{{{target}}}{{{display}}}"


def generate_reading_plan_tex(scheduled_entries: list[dict]) -> str:
    """Generate LaTeX reading-plan pages grouped by calendar month."""
    lines = []
    lines.append("% Reading Plan — Generated by generate_bible.py")

    current_month = None
    first_month = True

    for entry in scheduled_entries:
        month_key = entry["month_key"]

        # New month heading
        if month_key != current_month:
            current_month = month_key
            lines.append("\\clearpage")
            if first_month:
                # Clear the running-header marks: without this the plan pages
                # inherit the last scripture reference (Revelation 22:21).
                lines.append("\\markboth{}{}")
                lines.append("\\hypertarget{readingplan}{}")
                first_month = False
            lines.append("\\twocolumn[%")
            lines.append("  \\vspace*{20pt}%")
            lines.append(
                f"  {{\\centering\\huge\\booktitlefont\\scshape {month_key}\\\\%"
            )
            lines.append("  \\char\"2766\\par}%")
            lines.append("  \\vspace{10pt}%")
            lines.append("]")
            lines.append("")

        # Entry line with checkbox, date, and hyperlinked passage
        date_str = entry["date"]
        day_label = entry["day_label"]
        anchor = f"rp-{date_str}"
        passage = _entry_hyperlinks(entry)

        line = (
            f"\\hypertarget{{{anchor}}}{{}}\\noindent"
            f"$\\square$\\enspace {day_label}\\enspace---\\enspace "
            f"{passage}\\\\"
        )
        lines.append(line)

    lines.append("")
    return "\n".join(lines)
