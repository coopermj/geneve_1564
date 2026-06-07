"""Scrape 1599 Geneva Bible annotations from StudyLight and cache to JSON."""

import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_CACHE_DIR = os.path.join(_PROJECT_ROOT, "data", "annotations_cache")
_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "data", "geneva_annotations.json")
_BASE_URL = "https://www.studylight.org/commentaries/eng/gsb/{slug}-{chapter}.html"
_ANNOTATION_RE = re.compile(r'^\(([a-z]+)\)\s+(.*)', re.DOTALL)


def _dir_to_slug(book_dir: str) -> str:
    """Convert internal book directory slug to StudyLight URL slug."""
    if book_dir == "songofsolomon":
        return "song-of-solomon"
    return re.sub(r'^(\d+)([a-z])', r'\1-\2', book_dir)


def parse_chapter_html(html: str) -> dict[str, list[dict]]:
    """Parse StudyLight chapter HTML into {verse_str: [{letter, text}]}.

    Returns only verses that have at least one annotation.
    """
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, list[dict]] = {}

    verse_headers = [
        h for h in soup.find_all("h3")
        if re.match(r'^\s*Verse\s+(\d+)\s*$', h.get_text())
    ]

    for header in verse_headers:
        m = re.match(r'^\s*Verse\s+(\d+)\s*$', header.get_text())
        verse_num = m.group(1)
        annotations = []

        sibling = header.next_sibling
        while sibling is not None:
            if hasattr(sibling, 'name'):
                if sibling.name == 'h3':
                    break
                if sibling.name == 'p':
                    text = sibling.get_text(separator=' ', strip=True)
                    am = _ANNOTATION_RE.match(text)
                    if am:
                        annotations.append({
                            "letter": am.group(1),
                            "text": am.group(2).strip(),
                        })
            sibling = sibling.next_sibling

        if annotations:
            result[verse_num] = annotations

    return result


def _fetch_chapter_html(slug: str, chapter: int) -> str:
    """Fetch chapter HTML, using file cache. Returns empty string on error."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(_CACHE_DIR, f"{slug}-{chapter}.html")

    if os.path.isfile(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    url = _BASE_URL.format(slug=slug, chapter=chapter)
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"    WARNING: failed to fetch {url}: {e}")
        return ""

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)

    time.sleep(0.5)
    return html


def fetch_all_annotations(books) -> dict:
    """Scrape all books and return the full annotations dict."""
    all_annotations: dict = {}

    for book in books:
        slug = _dir_to_slug(book.directory)
        print(f"  {book.name} ({book.chapters} ch)...", end=" ", flush=True)
        book_data: dict = {}

        for ch in range(1, book.chapters + 1):
            html = _fetch_chapter_html(slug, ch)
            if not html:
                continue
            chapter_data = parse_chapter_html(html)
            if chapter_data:
                book_data[str(ch)] = chapter_data

        if book_data:
            all_annotations[book.directory] = book_data
        print("done")

    return all_annotations


def main():
    import sys
    sys.path.insert(0, _SCRIPT_DIR)
    from bible_config import BOOKS

    print("Fetching Geneva annotations from StudyLight...")
    print(f"Cache: {_CACHE_DIR}")
    print(f"Output: {_OUTPUT_PATH}")
    print()

    annotations = fetch_all_annotations(BOOKS)

    os.makedirs(os.path.dirname(_OUTPUT_PATH), exist_ok=True)
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)

    total_notes = sum(
        len(anns)
        for book in annotations.values()
        for ch in book.values()
        for anns in ch.values()
    )
    print(f"\nSaved {total_notes} annotations to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
