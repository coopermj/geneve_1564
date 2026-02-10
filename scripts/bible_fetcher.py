"""Fetch NET Bible text from labs.bible.org API with local JSON caching."""

import json
import os
import time
import urllib.parse

import requests

API_BASE = "https://labs.bible.org/api/"
DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "net_bible_cache",
)

MAX_RETRIES = 5
RETRY_DELAY = 3  # seconds


def _cache_path(cache_dir: str, book_abbrev: str, chapter: int) -> str:
    """Return the cache file path for a given book and chapter."""
    safe_name = book_abbrev.replace(" ", "_").lower()
    return os.path.join(cache_dir, f"{safe_name}_{chapter}.json")


def _parse_response(text: str) -> list[dict]:
    """Parse the API response, handling quirks like quote-wrapping."""
    body = text.strip()
    # Sometimes the response is wrapped in single quotes
    if body.startswith("'") and body.endswith("'"):
        body = body[1:-1]
    return json.loads(body)


def fetch_chapter(
    book_abbrev: str,
    chapter: int,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> list[dict]:
    """Fetch a single chapter from the API or local cache.

    Returns a list of verse dicts with keys: bookname, chapter, verse, text.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, book_abbrev, chapter)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    passage = f"{book_abbrev} {chapter}"
    params = {
        "passage": passage,
        "type": "json",
        "formatting": "full",
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            if not resp.text.strip():
                raise ValueError("Empty response body")

            data = _parse_response(resp.text)
            break
        except (json.JSONDecodeError, ValueError, requests.RequestException) as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                print(f"\n    Retry {attempt}/{MAX_RETRIES} for {passage} "
                      f"(error: {e}), waiting {wait}s...", end="", flush=True)
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Failed to fetch {passage} after {MAX_RETRIES} attempts: {e}"
                ) from e

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Be polite to the API
    time.sleep(0.5)
    return data


def fetch_book(
    book_abbrev: str,
    num_chapters: int,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> dict[int, list[dict]]:
    """Fetch all chapters for a book. Returns {chapter_num: [verse_dicts]}."""
    chapters = {}
    for ch in range(1, num_chapters + 1):
        chapters[ch] = fetch_chapter(book_abbrev, ch, cache_dir)
    return chapters
