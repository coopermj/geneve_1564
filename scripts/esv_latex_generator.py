"""Convert fetched ESV HTML to LaTeX using the scripture package, with full footnotes."""

import json
import os
import re
from html import unescape

from bible_config import BookInfo, BOOKS
from latex_generator import _chapter_table


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_POETRY_PATH = os.path.join(_SCRIPT_DIR, "poetry_sections.json")
_ARGUMENTS_PATH = os.path.join(_PROJECT_ROOT, "data", "geneva_arguments.json")

_poetry_config: dict | None = None


def _load_poetry_config() -> dict:
    global _poetry_config
    if _poetry_config is None:
        with open(_POETRY_PATH, "r", encoding="utf-8") as f:
            _poetry_config = json.load(f)
    return _poetry_config


def _is_poetry_chapter(book_dir: str, chapter: int) -> bool:
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


# ── LaTeX escaping ──────────────────────────────────────────────────────

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
    r"""Escape LaTeX specials in raw prose.

    Must be called on bare text BEFORE any LaTeX command (\textit, \vs,
    \markboth, \textsc, ...) is injected: it escapes literal ``\``, ``{``
    and ``}`` too, which would corrupt genuine commands if any were present.
    """
    return "".join(_LATEX_SPECIAL.get(ch, ch) for ch in text)


def _convert_smart_quotes(text: str) -> str:
    text = text.replace("\u201c", "``")
    text = text.replace("\u201d", "''")
    text = text.replace("\u2018", "`")
    text = text.replace("\u2019", "'")
    text = text.replace("\u2014", "---")
    text = text.replace("\u2013", "--")
    return text


def _apply_divine_names(text: str) -> str:
    r"""Replace LORD/GOD with \textsc{Lord}/\textsc{God}."""
    text = re.sub(r'\bLORD\b', r'\\textsc{Lord}', text)
    text = re.sub(r'\bGOD\b', r'\\textsc{God}', text)
    return text


# ── Heading images ──────────────────────────────────────────────────────

_HEADING_IMAGES = {
    "genesis": "images/genese_heading",
}


def _find_heading_image(book_dir: str) -> str | None:
    if book_dir in _HEADING_IMAGES:
        img_path = _HEADING_IMAGES[book_dir]
        if os.path.isfile(os.path.join(_PROJECT_ROOT, img_path + ".pdf")):
            return img_path
    convention_path = f"images/{book_dir}_heading"
    if os.path.isfile(os.path.join(_PROJECT_ROOT, convention_path + ".pdf")):
        return convention_path
    return None


# ── Lettrine ────────────────────────────────────────────────────────────

def _make_lettrine(text: str, lettrine_lines: int | None = None,
                   color: str | None = None) -> str:
    text = text.lstrip()
    prefix = ""
    if text.startswith("``"):
        prefix = "``"
        text = text[2:]
    elif text.startswith("`") and not text.startswith("``"):
        prefix = "`"
        text = text[1:]
    text = text.lstrip()
    if not text:
        return prefix + text

    first_letter = text[0]
    after_first = text[1:]
    match = re.match(r'([A-Za-z]*)(.*)', after_first, re.DOTALL)
    if match:
        rest_of_word = match.group(1)
        remainder = match.group(2)
    else:
        rest_of_word = ""
        remainder = after_first

    opts = f"[lines={lettrine_lines}]" if lettrine_lines else ""
    first_arg = f"\\color{{{color}}}{first_letter}" if color else first_letter
    second_arg = f"\\textsc{{{rest_of_word}}}" if rest_of_word else ""

    return f"{prefix}\\lettrine{opts}{{{first_arg}}}{{{second_arg}}}{remainder}"


# ── ESV HTML parsing ───────────────────────────────────────────────────

def _parse_footnotes(html: str) -> dict[str, str]:
    """Extract footnotes from the footnotes div, keyed by back-ref id (e.g. 'fb1-1')."""
    fn_div = re.search(r'<div class="footnotes[^"]*">(.*?)</div>', html, re.DOTALL)
    if not fn_div:
        return {}

    fn_html = fn_div.group(1)
    footnotes: dict[str, str] = {}

    # Each footnote entry has: <a href="#fbN-C" id="fN-C">[N]</a> ... <note ...>text</note>
    for m in re.finditer(
        r'<a[^>]*href="#(fb\d+-\d+)"[^>]*>\[\d+\]</a></span>'
        r'\s*<span class="footnote-ref">[^<]*</span>\s*'
        r'(.*?)(?=<br\s*/?>|\n<span class="footnote">|</p>)',
        fn_html,
        re.DOTALL,
    ):
        back_id = m.group(1)  # e.g. "fb1-1"
        fn_text = _clean_footnote_text(m.group(2))
        footnotes[back_id] = fn_text

    return footnotes


def _clean_footnote_text(text: str) -> str:
    """Convert footnote HTML to LaTeX-safe text.

    Prose is escaped BEFORE \\textit is injected, so literal braces/backslash
    in the note text are escaped without corrupting the injected command.
    """
    text = re.sub(r'</?note[^>]*>', '', text)
    text = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', text)
    text = unescape(text)
    # Escape bare prose first; <i> tags survive (no special chars), then
    # become \textit after escaping.
    text = _escape_latex(text)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'\\textit{\1}', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = _convert_smart_quotes(text)
    return text.strip()


def _strip_footnote_div(html: str) -> str:
    """Remove the footnotes div and copyright line from the end."""
    html = re.sub(r'<div class="footnotes.*', '', html, flags=re.DOTALL)
    html = re.sub(r'<p>\s*\(<a[^>]*>ESV</a>\)\s*</p>', '', html)
    return html


def _process_chapter_html(html: str, ch_num: int, book: BookInfo,
                          is_first_chapter: bool) -> list[str]:
    """Convert one chapter's body HTML into LaTeX lines.

    Returns a list of LaTeX lines for this chapter.
    """
    footnotes = _parse_footnotes(html)
    body = _strip_footnote_div(html)

    lines: list[str] = []
    is_poetry = _is_poetry_chapter(book.directory, ch_num)

    # Mark for running headers (verse 1 set here; subsequent verses inline)
    lines.append(f"\\markboth{{{book.name} {ch_num}:1}}{{{book.name} {ch_num}:1}}")

    if is_poetry:
        lines.append("\\begin{poetry}")

    # Footnote pattern — matched per-block below (not globally)
    _fn_pattern = re.compile(
        r'<sup class="footnote">\s*<a[^>]*id="(fb\d+-\d+)"[^>]*>\d+</a>\s*</sup>'
    )

    def _collect_and_replace_fns(block_html: str) -> tuple[str, str]:
        """Strip footnote markers from a block.

        Returns ``(clean_block, margin_note)``. The margin note (built from
        already-escaped footnote text) is returned separately so the caller
        can append it AFTER the block's prose is escaped -- appending it
        beforehand would let _escape_latex corrupt the \\marginnote braces.
        """
        matches = list(_fn_pattern.finditer(block_html))
        if not matches:
            return block_html, ""
        # Collect all footnote texts
        fn_texts = []
        for m in matches:
            fn_text = footnotes.get(m.group(1), "")
            if fn_text:
                fn_texts.append(fn_text)
        # Remove all footnote markers
        result = _fn_pattern.sub("", block_html)
        # Build combined margin note (appended by caller after escaping)
        note = ""
        if fn_texts:
            combined = " \\\\[1pt] ".join(fn_texts)
            note = f" \\marginnote{{\\tiny {combined}}}"
        return result, note

    # Apply per-block footnote grouping, then split
    # First strip the footnotes div so we don't process it
    # Split into block-level elements (h3 headings and p paragraphs)
    blocks = re.split(r'(?=<h3\b|<p\b)', body)

    first_verse_seen = False

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Strip footnote markers; the margin note is appended after escaping.
        block, margin_note = _collect_and_replace_fns(block)

        # Section heading
        h3 = re.match(r'<h3[^>]*>(.*?)</h3>', block)
        if h3:
            heading_text = re.sub(r'<[^>]+>', '', h3.group(1))
            heading_text = unescape(heading_text).strip()
            if heading_text.lower() == "footnotes":
                continue
            heading_text = _convert_smart_quotes(heading_text)
            heading_text = _escape_latex(heading_text)
            lines.append("")
            lines.append(
                f"\\begingroup\\parshape=0\\everypar{{}}"
                f"\\vspace{{\\baselineskip}}\\noindent"
                f"{{\\small\\itshape {heading_text}\\par}}"
                f"\\nobreak\\endgroup"
            )
            continue

        # Paragraph
        if not re.match(r'<p\b', block):
            continue

        # Check if this is a new paragraph (not the very first verse of ch)
        is_chapter_start = "starts-chapter" in block

        # Extract chapter number marker
        ch_match = re.search(
            r'<b class="chapter-num[^"]*"[^>]*>\s*\d+:\s*(\d+)[^<]*</b>',
            block,
        )

        para_text = block
        # Remove <p> and </p>
        para_text = re.sub(r'</?p[^>]*>', '', para_text)
        # Remove chapter-num <b> tag (we handle it separately)
        para_text = re.sub(r'<b class="chapter-num[^"]*"[^>]*>.*?</b>', '', para_text)
        # Mark woc spans with sentinels (\x01 open, \x02 close) so they
        # survive tag-stripping AND escaping; restored to redletter toggles
        # after escaping. Sentinels are control chars, never escaped.
        para_text = re.sub(r'<span class="woc">', '\x01', para_text)

        def _close_woc(text: str) -> str:
            depth = 0
            result = []
            i = 0
            while i < len(text):
                if text[i] == '\x01':
                    depth += 1
                    result.append('\x01')
                    i += 1
                elif text.startswith('</span>', i) and depth > 0:
                    result.append('\x02')
                    depth -= 1
                    i += len('</span>')
                else:
                    result.append(text[i])
                    i += 1
            return ''.join(result)
        para_text = _close_woc(para_text)

        # Replace verse-num <b> tags with a numeric sentinel (\x03 N \x04).
        # The real \markboth/\vs commands are restored AFTER escaping so the
        # command braces are not escaped.
        para_text = re.sub(
            r'<b class="verse-num[^"]*"[^>]*>\s*(\d+)[^<]*</b>',
            lambda m: f"\x03{m.group(1).strip()}\x04",
            para_text,
        )
        # Strip remaining HTML tags and decode entities -> bare prose.
        para_text = re.sub(r'<[^>]+>', '', para_text)
        para_text = unescape(para_text)
        # Escape bare prose BEFORE injecting any LaTeX commands.
        para_text = _escape_latex(para_text)
        # Inject commands into the now-escaped prose.
        para_text = _convert_smart_quotes(para_text)
        para_text = _apply_divine_names(para_text)

        # Restore verse-number sentinels -> running header + \vs.
        def _restore_verse(m: re.Match) -> str:
            v = m.group(1)
            mark = f"\\markboth{{{book.name} {ch_num}:{v}}}{{{book.name} {ch_num}:{v}}}"
            return f"{mark}\\vs{{{v}}} "
        para_text = re.sub('\x03(\\d+)\x04', _restore_verse, para_text)
        # Restore woc sentinels as redletter commands
        para_text = para_text.replace('\x01', '\\redletteron ')
        para_text = para_text.replace('\x02', '\\redletteroff ')
        para_text = re.sub(r'\s+', ' ', para_text).strip()
        # Append this block's combined footnote margin note (already escaped),
        # after escaping so its \marginnote braces survive intact.
        para_text = (para_text + margin_note).strip()

        if not para_text:
            continue

        if is_chapter_start and ch_match:
            # Chapter start — emit \ch{N} + lettrine.
            # Strip any leading \redletteron before passing to _make_lettrine
            # (lettrine must receive plain text as its first character).
            rl_prefix = ""
            lettrine_src = para_text
            if lettrine_src.startswith("\\redletteron "):
                rl_prefix = "\\redletteron "
                lettrine_src = lettrine_src[len("\\redletteron "):]
            if is_first_chapter and ch_num == 1:
                lettrine_text = _make_lettrine(
                    lettrine_src, lettrine_lines=8, color=book.group)
            else:
                lettrine_text = _make_lettrine(lettrine_src, lettrine_lines=5, color=book.group)
            lines.append(f"\\ch{{{ch_num}}} \\hypertarget{{ch-{book.directory}-{ch_num}}}{{}}{rl_prefix}{lettrine_text}\\everypar{{}}")
            first_verse_seen = True
        else:
            if first_verse_seen:
                lines.append("\\everypar{}")
                lines.append("")
                lines.append("\\parshape=0")
            lines.append(para_text)
            first_verse_seen = True

    if is_poetry:
        lines.append("\\end{poetry}")

    return lines


# ── Book-level generation ──────────────────────────────────────────────

def generate_book_tex(
    book: BookInfo,
    chapters_html: dict[int, str],
) -> str:
    """Generate the complete .tex content for an ESV book.

    Args:
        book: BookInfo metadata.
        chapters_html: {chapter_num: raw_html_string} from the fetcher.
    """
    lines = []
    lines.append(f"% {book.name} — Generated by generate_esv.py")
    lines.append(f"% ESV Bible text, scripture package formatting")

    heading_img = _find_heading_image(book.directory)
    escaped_title = _escape_latex(book.long_title)
    escaped_sub = _escape_latex(book.subtitle)
    argument = _escape_latex(_load_argument(book.directory) or "")
    sorted_chapters = sorted(chapters_html.keys())
    ch_table = _chapter_table(book.directory, sorted_chapters)
    lines.append(f"\\gdef\\bbookchaptable{{{ch_table}}}")
    if heading_img:
        lines.append(f"\\bbook[{heading_img}]{{{escaped_title}}}{{{escaped_sub}}}{{{argument}}}{{{book.directory}}}")
    else:
        lines.append(f"\\bbook{{{escaped_title}}}{{{escaped_sub}}}{{{argument}}}{{{book.directory}}}")

    lines.append("")
    lines.append("\\begin{scripture}")

    for ch_num in sorted_chapters:
        html = chapters_html[ch_num]
        is_first = (ch_num == sorted_chapters[0])
        ch_lines = _process_chapter_html(html, ch_num, book, is_first)
        lines.append("")
        lines.extend(ch_lines)

    lines.append("")
    lines.append("\\end{scripture}")
    lines.append("")

    return "\n".join(lines)


# ── Color index & testament files ──────────────────────────────────────

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

# After these groups, force a column break (produces 3 columns: OT1 | OT2 | NT)
_COLUMN_BREAK_AFTER = {"wisdom", "minorprophets"}


def generate_color_index_tex() -> str:
    lines = []
    lines.append("% Color Index — Generated by generate_esv.py")
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


def generate_testament_tex(books: list, testament_label: str,
                           subdir: str = "livres_esv") -> str:
    lines = []
    lines.append(f"% {testament_label} — Generated by generate_esv.py")
    for book in books:
        lines.append(f"\\input{{{subdir}/{book.directory}/{book.directory}}}")
    lines.append("")
    return "\n".join(lines)
