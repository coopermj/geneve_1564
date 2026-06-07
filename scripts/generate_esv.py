#!/usr/bin/env python3
"""Generate LaTeX .tex files for the ESV Bible with full footnotes.

Usage:
    python3 scripts/generate_esv.py                    # Generate all 66 books
    python3 scripts/generate_esv.py --books genesis     # Generate specific books
"""

import argparse
import os
import sys

from dotenv import load_dotenv

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

sys.path.insert(0, _SCRIPT_DIR)

from bible_config import BOOKS, get_book_by_name, get_books_by_testament
from esv_fetcher import fetch_chapter
from esv_latex_generator import (
    generate_book_tex,
    generate_testament_tex,
)

ESV_API_KEY = os.environ.get("ESV_API_KEY", "")


def fetch_book(book_name: str, num_chapters: int, api_key: str,
               cache_dir: str) -> dict[int, str]:
    """Fetch all chapters of a book, returning {chapter_num: html}."""
    import time as _time
    chapters = {}
    for ch in range(1, num_chapters + 1):
        html = fetch_chapter(book_name, ch, api_key, cache_dir)
        chapters[ch] = html
        _time.sleep(0.4)  # gentle rate-limit buffer between chapters
    return chapters


def run_esv(output_dir: str, cache_dir: str, books=None) -> None:
    """Generate ESV book .tex + testament includes into output_dir (offline from cache)."""
    books_to_generate = books if books else BOOKS
    print(f"[esv] Generating {len(books_to_generate)} book(s) -> {output_dir}")
    for book in books_to_generate:
        chapters_html = fetch_book(book.name, book.chapters, ESV_API_KEY, cache_dir)
        tex_content = generate_book_tex(book, chapters_html)
        book_dir = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir, exist_ok=True)
        with open(os.path.join(book_dir, f"{book.directory}.tex"), "w", encoding="utf-8") as f:
            f.write(tex_content)
    all_ot = get_books_by_testament("OT")
    all_nt = get_books_by_testament("NT")
    gen = {b.directory for b in books_to_generate}
    if {b.directory for b in all_ot} <= gen:
        with open(os.path.join(output_dir, "old_testament.tex"), "w", encoding="utf-8") as f:
            f.write(generate_testament_tex(all_ot, "Old Testament"))
    if {b.directory for b in all_nt} <= gen:
        with open(os.path.join(output_dir, "new_testament.tex"), "w", encoding="utf-8") as f:
            f.write(generate_testament_tex(all_nt, "New Testament"))


def main():
    parser = argparse.ArgumentParser(description="Generate LaTeX files for the ESV Bible")
    parser.add_argument("--books", nargs="+")
    parser.add_argument("--output-dir", default=os.path.join(_PROJECT_ROOT, "livres_esv"))
    parser.add_argument("--cache-dir", default=os.path.join(_PROJECT_ROOT, "data", "esv_cache"))
    args = parser.parse_args()
    books = [get_book_by_name(n) for n in args.books] if args.books else None
    if books and any(b is None for b in books):
        print("Error: unknown book", file=sys.stderr); sys.exit(1)
    run_esv(args.output_dir, args.cache_dir, books)
    print("Done!")


if __name__ == "__main__":
    main()
