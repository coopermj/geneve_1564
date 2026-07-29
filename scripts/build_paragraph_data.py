#!/usr/bin/env python3
"""Derive prose paragraph boundaries from the WEB USFM and write them as
data/paragraph_starts.json = {book_dir: {chapter: [verse, ...]}}.

The public-domain KJV text (aruljohn) carries no paragraph structure, so a KJV
edition rendered through the shared generator runs every chapter together as one
paragraph AND never fires the lettrine \\parshape/\\everypar reset (throwing the
chapter markers off-centre). The WEB USFM I already use for red-letter has \\p
paragraph markers; WEB and KJV share versification, so a verse that opens a
paragraph in WEB opens one in the KJV edition too. kjv_fetcher injects a
<p> tag at these verses so the generator's existing paragraph handling fires.

Poetry markers (\\q...) are intentionally excluded: poetry chapters are handled
by poetry_sections.json, not by prose paragraphing.
"""
import glob
import json
import os
import re

from build_red_letter_data import _USFM_DIR

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT = os.path.join(_ROOT, "data", "paragraph_starts.json")

# Full USFM 3-letter code -> book directory, all 66 Protestant-canon books
# (apocrypha codes present in the WEB USFM are simply not listed → skipped).
_CODE_TO_DIR = {
    "GEN": "genesis", "EXO": "exodus", "LEV": "leviticus", "NUM": "numbers",
    "DEU": "deuteronomy", "JOS": "joshua", "JDG": "judges", "RUT": "ruth",
    "1SA": "1samuel", "2SA": "2samuel", "1KI": "1kings", "2KI": "2kings",
    "1CH": "1chronicles", "2CH": "2chronicles", "EZR": "ezra", "NEH": "nehemiah",
    "EST": "esther", "JOB": "job", "PSA": "psalms", "PRO": "proverbs",
    "ECC": "ecclesiastes", "SNG": "songofsolomon", "ISA": "isaiah",
    "JER": "jeremiah", "LAM": "lamentations", "EZK": "ezekiel", "DAN": "daniel",
    "HOS": "hosea", "JOL": "joel", "AMO": "amos", "OBA": "obadiah", "JON": "jonah",
    "MIC": "micah", "NAM": "nahum", "HAB": "habakkuk", "ZEP": "zephaniah",
    "HAG": "haggai", "ZEC": "zechariah", "MAL": "malachi", "MAT": "matthew",
    "MRK": "mark", "LUK": "luke", "JHN": "john", "ACT": "acts", "ROM": "romans",
    "1CO": "1corinthians", "2CO": "2corinthians", "GAL": "galatians",
    "EPH": "ephesians", "PHP": "philippians", "COL": "colossians",
    "1TH": "1thessalonians", "2TH": "2thessalonians", "1TI": "1timothy",
    "2TI": "2timothy", "TIT": "titus", "PHM": "philemon", "HEB": "hebrews",
    "JAS": "james", "1PE": "1peter", "2PE": "2peter", "1JN": "1john",
    "2JN": "2john", "3JN": "3john", "JUD": "jude", "REV": "revelation",
}

# Prose paragraph-opening markers (USFM). \p is the workhorse; the others are
# indented/embedded/closing prose paragraphs. Poetry (\q*) and list items are
# deliberately omitted.
_PARA = re.compile(r"\\(p|m|pi\d?|pc|pr|pmo|pm|pmc|pmr|nb|cls)\b")
_C = re.compile(r"\\c\s+(\d+)")
_V = re.compile(r"\\v\s+(\d+)")


def parse_paragraph_starts(filepath: str) -> dict[str, list[int]]:
    """Return {chapter_str: [verse_ints that open a prose paragraph]}."""
    out: dict[str, list[int]] = {}
    ch = None
    pending = False  # a paragraph marker has been seen since the last \v
    for line in open(filepath, encoding="utf-8"):
        line = line.strip()
        mc = _C.match(line)
        if mc:
            ch = mc.group(1)
            pending = False
            continue
        if _PARA.match(line):
            pending = True
            continue
        mv = _V.match(line)
        if mv and ch is not None:
            if pending:
                out.setdefault(ch, []).append(int(mv.group(1)))
            pending = False
    return out


def main() -> None:
    data: dict[str, dict[str, list[int]]] = {}
    for fp in sorted(glob.glob(os.path.join(_USFM_DIR, "*.usfm"))):
        m = re.search(r"\d+-([A-Z1-9]{3})", os.path.basename(fp))
        if not m or m.group(1) not in _CODE_TO_DIR:
            continue
        book_dir = _CODE_TO_DIR[m.group(1)]
        starts = parse_paragraph_starts(fp)
        if starts:
            data[book_dir] = starts
    with open(_OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    total = sum(len(v) for b in data.values() for v in b.values())
    print(f"Wrote {_OUT}: {len(data)} books, {total} paragraph-start verses")


if __name__ == "__main__":
    main()
