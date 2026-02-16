#!/usr/bin/env python3
"""Fetch 'The Argument' prologues from the 1599 Geneva Bible via BibleHub GSB.

Saves to data/geneva_arguments.json keyed by book directory name.
Source: https://biblehub.com/commentaries/gsb/{book}/1.htm
"""

import json
import os
import re
import sys
import time
from html import unescape

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bible_config import BOOKS

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "data", "geneva_arguments.json")

# BibleHub URL slugs (lowercase, underscores for spaces)
_BH_SLUGS = {
    "1samuel": "1_samuel",
    "2samuel": "2_samuel",
    "1kings": "1_kings",
    "2kings": "2_kings",
    "1chronicles": "1_chronicles",
    "2chronicles": "2_chronicles",
    "songofsolomon": "songs",
    "1corinthians": "1_corinthians",
    "2corinthians": "2_corinthians",
    "1thessalonians": "1_thessalonians",
    "2thessalonians": "2_thessalonians",
    "1timothy": "1_timothy",
    "2timothy": "2_timothy",
    "1peter": "1_peter",
    "2peter": "2_peter",
    "1john": "1_john",
    "2john": "2_john",
    "3john": "3_john",
}


def _get_bh_slug(book_dir: str) -> str:
    return _BH_SLUGS.get(book_dir, book_dir)


def _fetch_argument(book_dir: str) -> str | None:
    """Fetch the Geneva 'Argument' for one book from BibleHub GSB commentary."""
    slug = _get_bh_slug(book_dir)
    url = f"https://biblehub.com/commentaries/gsb/{slug}/1.htm"

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            if resp.status_code == 200 and resp.text.strip():
                break
        except requests.RequestException as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
        time.sleep(2)
    else:
        print(f"  Failed to fetch {slug}")
        return None

    html = resp.text

    # BibleHub format: "The Argument - <text>...<p>" as inline text
    # ending at a <p> tag or <div class="versenum"> (next verse block)
    m = re.search(
        r'The\s+Argument\s*[-\u2013\u2014]?\s*(.*?)(?:<p>|<div\s+class="versenum")',
        html, re.DOTALL | re.IGNORECASE,
    )
    if m:
        text = _clean_text(m.group(1))
        if len(text) > 30:
            return text

    # Broader fallback: grab text after "The Argument" up to next </div>
    m2 = re.search(
        r'The\s+Argument\s*[-\u2013\u2014]?\s*(.*?)</div>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if m2:
        text = _clean_text(m2.group(1))
        if len(text) > 30:
            return text

    return None


def _clean_text(html_text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r'<[^>]+>', '', html_text)
    text = unescape(text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def main():
    # Load existing if present (for incremental updates)
    arguments: dict[str, str] = {}
    if os.path.exists(_OUTPUT_PATH):
        with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
            arguments = json.load(f)

    for book in BOOKS:
        if book.directory in arguments and arguments[book.directory]:
            print(f"  {book.name}: already cached")
            continue

        print(f"Fetching argument for {book.name}...")
        arg = _fetch_argument(book.directory)
        if arg:
            arguments[book.directory] = arg
            print(f"  {book.name}: OK ({len(arg)} chars)")
        else:
            print(f"  {book.name}: no argument found")
            arguments[book.directory] = ""

        time.sleep(1.0)  # rate limit

    os.makedirs(os.path.dirname(_OUTPUT_PATH), exist_ok=True)
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(arguments, f, indent=2, ensure_ascii=False)

    found = sum(1 for v in arguments.values() if v)
    print(f"\nDone. {found}/{len(BOOKS)} arguments saved to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
