"""Convert fetched NET Bible verse data to LaTeX using the scripture package."""

import json
import os
import re

from bible_config import BookInfo, BOOKS


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_POETRY_PATH = os.path.join(_SCRIPT_DIR, "poetry_sections.json")

_poetry_config: dict | None = None


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


# LaTeX special characters that need escaping
_LATEX_SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape_latex(text: str) -> str:
    """Escape LaTeX special characters, but preserve existing commands."""
    # We process character by character, skipping backslash sequences
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            # Keep backslash sequences as-is (LaTeX commands)
            result.append(ch)
            i += 1
        elif ch in _LATEX_SPECIAL:
            result.append(_LATEX_SPECIAL[ch])
            i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def _strip_html_tags(html: str) -> str:
    """Strip HTML tags from API response, converting notes to footnotes.

    The API returns:
    - <st data-num="XXXX" class="">word</st>  -> just keep the word
    - <n id="N" />  -> translator note markers (we skip these for now)
    - <p class="bodytext">...</p>  -> paragraph wrappers
    - Smart quotes: \u201c \u201d \u2018 \u2019
    """
    text = html

    # Remove <p> tags
    text = re.sub(r'</?p[^>]*>', '', text)

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
    # Handle LaTeX opening double quotes
    if text.startswith("``"):
        prefix = "``"
        text = text[2:]
    # Handle LaTeX opening single quote
    elif text.startswith("`") and not text.startswith("``"):
        prefix = "`"
        text = text[1:]

    # Skip any leading whitespace after quotes
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


def _starts_paragraph(raw_html: str) -> bool:
    """Check if this verse starts a new paragraph (has a <p> tag)."""
    return bool(re.search(r'<p\b[^>]*>', raw_html))


def _process_verse_text(raw_html: str) -> str:
    """Full pipeline: strip HTML, convert quotes, escape, apply divine names."""
    text = _strip_html_tags(raw_html)
    text = _convert_smart_quotes(text)
    text = _apply_divine_names(text)
    text = _escape_latex(text)
    return text


def generate_book_tex(
    book: BookInfo,
    chapters_data: dict[int, list[dict]],
) -> str:
    """Generate the complete .tex content for a book.

    Args:
        book: BookInfo with name, directory, group, long_title, subtitle, etc.
        chapters_data: {chapter_num: [verse_dicts]} from the fetcher
    """
    lines = []
    lines.append(f"% {book.name} — Generated by generate_bible.py")
    lines.append(f"% NET Bible text, scripture package formatting")

    heading_img = _find_heading_image(book.directory)
    # Emit \bbook[image]{Long Title}{Subtitle}
    escaped_title = book.long_title
    escaped_sub = book.subtitle
    if heading_img:
        lines.append(f"\\bbook[{heading_img}]{{{escaped_title}}}{{{escaped_sub}}}")
    else:
        lines.append(f"\\bbook{{{escaped_title}}}{{{escaped_sub}}}")

    lines.append("")
    lines.append("\\begin{scripture}")

    sorted_chapters = sorted(chapters_data.keys())

    for ch_num in sorted_chapters:
        verses = chapters_data[ch_num]
        is_poetry = _is_poetry_chapter(book.directory, ch_num)

        lines.append("")

        if is_poetry:
            lines.append("\\begin{poetry}")

        for verse in verses:
            verse_num = int(verse["verse"])
            raw_html = verse["text"]
            new_para = _starts_paragraph(raw_html)
            text = _process_verse_text(raw_html)

            if verse_num == 1:
                # Chapter start — use \ch{N} with lettrine drop cap
                # Chapter 1 gets a larger 5-line lettrine
                if ch_num == 1:
                    lettrine_text = _make_lettrine(
                        text, lettrine_lines=5, color=book.group)
                else:
                    lettrine_text = _make_lettrine(text, color=book.group)
                lines.append(f"\\markboth{{{book.name}~{ch_num}:1}}{{{book.name}~{ch_num}:1}}")
                lines.append(f"\\ch{{{ch_num}}} {lettrine_text}")
            else:
                # Insert blank line for paragraph breaks, but suppress
                # the first one after verse 1 so the lettrine flows.
                # Reset \parshape to prevent lettrine indent from bleeding.
                if new_para and verse_num > 2:
                    lines.append("")
                    lines.append("\\parshape=0")
                mark = f"\\markboth{{{book.name}~{ch_num}:{verse_num}}}{{{book.name}~{ch_num}:{verse_num}}}"
                lines.append(f"{mark}\\vs{{{verse_num}}} {text}")

        if is_poetry:
            lines.append("\\end{poetry}")

    lines.append("")
    lines.append("\\end{scripture}")
    lines.append("")

    return "\n".join(lines)


def generate_testament_tex(books: list, testament_label: str) -> str:
    """Generate old_testament.tex or new_testament.tex with \\input lines."""
    lines = []
    lines.append(f"% {testament_label} — Generated by generate_bible.py")
    for book in books:
        lines.append(f"\\input{{livres/{book.directory}/{book.directory}}}")
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


def generate_color_index_tex() -> str:
    """Generate a color index page grouping books by their color-coded category."""
    lines = []
    lines.append("% Color Index — Generated by generate_bible.py")
    lines.append("\\clearpage")
    lines.append("\\thispagestyle{empty}")
    lines.append("\\hypertarget{toc}{}")
    lines.append("\\twocolumn[%")
    lines.append("  \\vspace*{20pt}%")
    lines.append("  {\\centering\\huge\\booktitlefont\\scshape Index of Books"
                  "\\\\\\char\"2766\\par}%")
    lines.append("  \\vspace{10pt}%")
    lines.append("]")
    lines.append("")

    # Build a lookup: group -> list of BookInfo
    group_books: dict[str, list[BookInfo]] = {}
    for book in BOOKS:
        group_books.setdefault(book.group, []).append(book)

    for group_key, group_label in _GROUP_INFO:
        books = group_books.get(group_key, [])
        if not books:
            continue
        lines.append(f"\\noindent{{\\bfseries\\color{{{group_key}}}{group_label}}}\\\\")
        for book in books:
            lines.append(f"\\hspace{{1em}}{book.name}\\\\")
        lines.append("\\medskip")
        lines.append("")

    lines.append("")
    return "\n".join(lines)
