"""Fetch ESV Bible text from api.esv.org with caching."""

import json
import os
import time

import requests

ESV_API_URL = "https://api.esv.org/v3/passage/html/"


def fetch_chapter(
    book_name: str,
    chapter: int,
    api_key: str,
    cache_dir: str,
    retries: int = 5,
) -> str:
    """Fetch a single chapter's HTML from the ESV API, with file caching.

    Returns the raw HTML string for the chapter.
    """
    safe_name = book_name.lower().replace(" ", "_")
    cache_file = os.path.join(cache_dir, f"{safe_name}_{chapter}.json")

    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)["html"]

    # Single-chapter books: the ESV API reads "Jude 1" as VERSE 1, not
    # chapter 1, silently truncating the book. Request "Jude 1:1-1:25"-style
    # full-chapter form via "Book 1:1-999" (the API clamps to the real end).
    _SINGLE_CHAPTER = {"Obadiah", "Philemon", "2 John", "3 John", "Jude"}
    if book_name in _SINGLE_CHAPTER:
        passage = f"{book_name} 1:1-1:999"
    else:
        passage = f"{book_name} {chapter}"

    for attempt in range(retries):
        try:
            resp = requests.get(
                ESV_API_URL,
                headers={"Authorization": f"Token {api_key}"},
                params={
                    "q": passage,
                    "include-footnotes": "true",
                    "include-verse-numbers": "true",
                    "include-chapter-numbers": "true",
                    "include-headings": "true",
                    "include-css-link": "false",
                    "include-passage-references": "false",
                    "include-audio-link": "false",
                    "include-short-copyright": "false",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            passages = data.get("passages", [])
            if not passages or not passages[0].strip():
                raise ValueError("Empty passage returned")

            html = passages[0]
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump({"html": html, "passage": passage}, f)
            return html

        except Exception as e:
            if attempt == retries - 1:
                raise
            # Use longer delays for rate-limit (429) errors
            is_429 = "429" in str(e)
            delay = (30 * (attempt + 1)) if is_429 else (3 * (attempt + 1))
            print(
                f"    Retry {attempt+1}/{retries} for {passage}"
                f" (error: {e}), waiting {delay}s..."
            )
            time.sleep(delay)

    raise RuntimeError(f"Failed to fetch {passage} after {retries} retries")
