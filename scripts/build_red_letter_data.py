#!/usr/bin/env python3
"""Parse WEB USFM files to extract red-letter (words of Christ) verse data.

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
