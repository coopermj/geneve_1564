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

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bible_config import BOOKS, get_book_by_name, get_books_by_testament
from esv_fetcher import fetch_chapter
from esv_latex_generator import (
    generate_book_tex,
    generate_testament_tex,
    generate_color_index_tex,
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate LaTeX files for the ESV Bible"
    )
    parser.add_argument(
        "--books",
        nargs="+",
        help="Specific books to generate (by name or slug). Default: all 66.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "livres_esv",
        ),
        help="Output directory (default: livres_esv/)",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "esv_cache",
        ),
        help="Cache directory for API responses (default: data/esv_cache/)",
    )
    args = parser.parse_args()

    if args.books:
        books_to_generate = []
        for name in args.books:
            book = get_book_by_name(name)
            if book is None:
                print(f"Error: Unknown book '{name}'", file=sys.stderr)
                sys.exit(1)
            books_to_generate.append(book)
    else:
        books_to_generate = BOOKS

    output_dir = args.output_dir
    cache_dir = args.cache_dir

    print(f"Generating {len(books_to_generate)} ESV book(s)...")
    print(f"Output: {output_dir}")
    print(f"Cache:  {cache_dir}")
    print()

    for book in books_to_generate:
        print(f"  {book.name} ({book.chapters} chapters)...", end=" ", flush=True)

        chapters_html = fetch_book(
            book.name, book.chapters, ESV_API_KEY, cache_dir
        )

        tex_content = generate_book_tex(book, chapters_html)

        book_dir = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir, exist_ok=True)
        tex_path = os.path.join(book_dir, f"{book.directory}.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        print("done")

    print()
    print("Generating testament include files...")

    ot_books = [b for b in books_to_generate if b.testament == "OT"]
    nt_books = [b for b in books_to_generate if b.testament == "NT"]

    all_ot = get_books_by_testament("OT")
    all_nt = get_books_by_testament("NT")

    if set(b.directory for b in ot_books) == set(b.directory for b in all_ot):
        ot_tex = generate_testament_tex(all_ot, "Old Testament")
        ot_path = os.path.join(output_dir, "old_testament.tex")
        with open(ot_path, "w", encoding="utf-8") as f:
            f.write(ot_tex)
        print("  old_testament.tex written")
    elif ot_books:
        print("  (skipping old_testament.tex — not all OT books generated)")

    if set(b.directory for b in nt_books) == set(b.directory for b in all_nt):
        nt_tex = generate_testament_tex(all_nt, "New Testament")
        nt_path = os.path.join(output_dir, "new_testament.tex")
        with open(nt_path, "w", encoding="utf-8") as f:
            f.write(nt_tex)
        print("  new_testament.tex written")
    elif nt_books:
        print("  (skipping new_testament.tex — not all NT books generated)")

    index_tex = generate_color_index_tex()
    index_path = os.path.join(output_dir, "color_index.tex")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_tex)
    print("  color_index.tex written")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
