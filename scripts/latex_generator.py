"""Convert fetched NET Bible verse data to LaTeX using the scripture package."""

import json
import os
import re

from bible_config import BookInfo, BOOKS


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


def _chapter_table(book_dir: str, chapter_nums: list[int]) -> str:
    """Return a one-line compact chapter navigation table for the book heading.

    Renders as a centred, single-line row of chapter numbers (in small italic)
    separated by thin spaces, each a PDF hyperlink to its chapter target
    (ch-{book_dir}-{N}).  The whole row is wrapped in \\twocolumn[...] so it
    appears full-width above the two text columns on the book title page.
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
    # Strip all leading LaTeX opening quotes (`` and/or `) and open parens
    # Handles nested quotes like ``\`You... (double-then-single)
    while text.startswith("``") or text.startswith("`") or text.startswith("("):
        if text.startswith("``"):
            prefix += "``"
            text = text[2:]
        elif text.startswith("`"):
            prefix += "`"
            text = text[1:]
        else:
            prefix += "("
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
        manifest.append({"idx": idx, "book": book_dir, "ch": ch_num,
                          "verse": verse_num, "letter": ann["letter"]})

        letter = ann["letter"]
        text = _escape_latex(_convert_smart_quotes(ann["text"]))
        inline = f"\\gva{{{letter}}}"
        note_content = f"\\gva{{{letter}}}\\,{text}"

        correction = corrections.get(idx, 0) if corrections else 0
        if correction == "footnote":
            parts.append(f"{inline}\\footnote{{{note_content}}}")
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
    escaped_title = book.long_title
    escaped_sub = book.subtitle
    argument = _load_argument(book.directory) or ""
    sorted_chapters = sorted(chapters_data.keys())
    ch_table = _chapter_table(book.directory, sorted_chapters)
    lines.append(f"\\gdef\\bbookchaptable{{{ch_table}}}")
    if heading_img:
        lines.append(f"\\bbook[{heading_img}]{{{escaped_title}}}{{{escaped_sub}}}{{{argument}}}{{{book.directory}}}")
    else:
        lines.append(f"\\bbook{{{escaped_title}}}{{{escaped_sub}}}{{{argument}}}{{{book.directory}}}")

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

        for verse in verses:
            verse_num = int(verse["verse"])
            raw_html = verse["text"]
            new_para = _starts_paragraph(raw_html)
            text = _process_verse_text(raw_html)

            ch_annotations = _book_annotations.get(str(ch_num), {})
            verse_anns = ch_annotations.get(str(verse_num), [])
            ann_suffix = _build_annotation_suffix(
                book.directory, ch_num, verse_num, verse_anns,
                _counter, _manifest, corrections
            )

            if verse_num == 1:
                # Chapter start — use \ch{N} with lettrine drop cap
                if ch_num == 1:
                    lettrine_text = _make_lettrine(
                        text, lettrine_lines=8, color=book.group)
                    lettrine_char_budget = 8 * 80
                else:
                    lettrine_text = _make_lettrine(text, lettrine_lines=5, color=book.group)
                    lettrine_char_budget = 5 * 80
                lettrine_char_budget -= len(text)
                lines.append(f"\\markboth{{{book.name} {ch_num}:1}}{{{book.name} {ch_num}:1}}")
                # Ensure enough vertical space for the chapter heading +
                # lettrine before starting.  Without this, the scripture
                # package's \nobreak glues heading to verse 1, and when the
                # lettrine is too tall for the remaining column TeX pushes
                # the whole block out, leaving large blank gaps.
                if ch_num > 1:
                    lines.append("\\Needspace*{8\\baselineskip}")
                lines.append(f"\\ch{{{ch_num}}} \\allowchapbreak\\hypertarget{{ch-{book.directory}-{ch_num}}}{{}}{lettrine_text}{ann_suffix}\\everypar{{}}")
            else:
                lettrine_char_budget -= len(text)
                mark = f"\\markboth{{{book.name} {ch_num}:{verse_num}}}{{{book.name} {ch_num}:{verse_num}}}"
                if new_para:
                    if lettrine_char_budget > 0 and not is_poetry:
                        # Within lettrine zone: line break (not \par) to
                        # preserve \parshape and avoid drop-cap overlap.
                        # Skipped in poetry: \obeylines makes \\ invalid.
                        lines.append(f"\\\\\\indent{mark}\\vs{{{verse_num}}} {text}{ann_suffix}")
                    else:
                        lines.append("\\everypar{}")
                        lines.append("")
                        lines.append("\\parshape=0")
                        lines.append(f"{mark}\\vs{{{verse_num}}} {text}{ann_suffix}")
                else:
                    lines.append(f"{mark}\\vs{{{verse_num}}} {text}{ann_suffix}")

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
            lines.append(f"\\hspace{{1em}}\\hyperlink{{book-{book.directory}}}{{{book.name}}}\\\\")
        lines.append("\\medskip")
        lines.append("")

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
