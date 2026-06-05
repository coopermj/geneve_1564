#!/usr/bin/env python3
r"""Parse WEB USFM files to extract red-letter (words of Christ) verse data.

The World English Bible (WEB) USFM files use \wj ... \wj* markers for words
of Jesus. We parse these to produce a verse-level red-letter map that the NET
generator can use to mark entire verses with \redletteron / \redletteroff.

Output: data/red_letter_verses.json
Format: {"book_dir": {"chapter": [verse_nums], ...}, ...}
"""

import glob
import json
import os
import re

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_USFM_DIR = os.path.join(_PROJECT_ROOT, "data", "engweb_usfm")
_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "data", "red_letter_verses.json")

# USFM 3-letter book code → our book directory name
_CODE_TO_DIR = {
    "MAT": "matthew",
    "MRK": "mark",
    "LUK": "luke",
    "JHN": "john",
    "ACT": "acts",
    "REV": "revelation",
}


def _clean_web_verse(raw: str) -> str:
    r"""Strip USFM markup from a verse, marking \wj spans with sentinels.

    Returns plain text where '\x01' marks a words-of-Jesus span opening and
    '\x02' marks its close. Footnotes (\f..\f*) and cross-references
    (\x..\x*) are removed entirely (they contain quotes we must not count).
    """
    t = raw
    # Remove footnotes and cross-references (may contain quotes/markers).
    t = re.sub(r"\\f .*?\\f\*", "", t)
    t = re.sub(r"\\x .*?\\x\*", "", t)
    # Mark words-of-Jesus spans with sentinels (\wj* before \wj to be safe).
    t = t.replace(r"\wj*", "\x02")
    t = re.sub(r"\\wj\b", "\x01", t)
    # Unwrap word markup: \+w word|strong=..\+w*  and  \w word|..\w*  -> word
    t = re.sub(r"\\\+w ([^\\|]*)(?:\|[^\\]*?)?\\\+w\*", r"\1", t)
    t = re.sub(r"\\w ([^\\|]*)(?:\|[^\\]*?)?\\w\*", r"\1", t)
    # Drop any remaining USFM markers (\q1, \q2, \p, \m, \b, \nb, ...).
    t = re.sub(r"\\[a-z]+\d*\*?", " ", t)
    return t


def parse_verse_descriptor(raw: str):
    r"""Return {"opens": [bool...], "starts_in_jesus": bool} or None.

    opens: one flag per TOP-LEVEL double-quote open in the verse, in order;
           True if that quote begins inside a \wj (Jesus) span.
    starts_in_jesus: the verse's first content begins inside a \wj span with
           no opening double quote (a continuation verse).
    Returns None if the verse contains no Words of Christ.
    """
    t = _clean_web_verse(raw)
    in_wj = False
    depth = 0
    opens: list[bool] = []
    starts = False
    seen = False
    jesus = False
    for ch in t:
        if ch == "\x01":
            in_wj = True
            continue
        if ch == "\x02":
            in_wj = False
            continue
        if ch == "“":  # open double
            if depth == 0:
                opens.append(in_wj)
            if in_wj:
                jesus = True
            depth += 1
            seen = True
            continue
        if ch == "”":  # close double
            depth = max(0, depth - 1)
            seen = True
            continue
        if ch.isspace():
            continue
        if not seen:
            seen = True
            if in_wj and depth == 0:
                starts = True
        if in_wj:
            jesus = True
    if not jesus:
        return None
    return {"opens": opens, "starts_in_jesus": starts}


def parse_usfm_for_wj(filepath: str) -> dict[str, list[int]]:
    """Return {chapter_str: [verse_nums_with_wj]} for one USFM file."""
    result: dict[str, list[int]] = {}
    current_chapter: int | None = None
    current_verse: int | None = None
    verse_parts: list[str] = []

    def flush():
        if current_chapter is not None and current_verse is not None:
            text = " ".join(verse_parts)
            if r"\wj" in text:
                ch = str(current_chapter)
                result.setdefault(ch, []).append(current_verse)

    with open(filepath, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if re.match(r"\\c\s+\d+", line):
                flush()
                verse_parts = []
                current_verse = None
                current_chapter = int(re.match(r"\\c\s+(\d+)", line).group(1))
            elif re.match(r"\\v\s+\d+", line):
                flush()
                m = re.match(r"\\v\s+(\d+)\s*(.*)", line)
                current_verse = int(m.group(1))
                verse_parts = [m.group(2)]
            elif current_verse is not None:
                verse_parts.append(line)

    flush()
    return result


def main() -> None:
    all_data: dict[str, dict[str, list[int]]] = {}

    for filepath in sorted(glob.glob(os.path.join(_USFM_DIR, "*.usfm"))):
        filename = os.path.basename(filepath)
        m = re.search(r"\d+-([A-Z1-9]{3})", filename)
        if not m:
            continue
        code = m.group(1)
        if code not in _CODE_TO_DIR:
            continue

        book_dir = _CODE_TO_DIR[code]
        data = parse_usfm_for_wj(filepath)
        if data:
            all_data[book_dir] = data
            total = sum(len(v) for v in data.values())
            print(f"  {book_dir}: {total} red-letter verses across {len(data)} chapters")

    with open(_OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(all_data, fh, indent=2)

    print(f"\nWrote {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
