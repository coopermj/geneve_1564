#!/usr/bin/env python3
"""Generate LaTeX .tex files for the NET Bible using the scripture package.

Usage:
    python3 scripts/generate_bible.py                    # Generate all 66 books
    python3 scripts/generate_bible.py --books genesis     # Generate specific books
    python3 scripts/generate_bible.py --books genesis exodus psalms
"""

import argparse
import os
import sys

# Ensure the scripts directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bible_config import BOOKS, get_book_by_name, get_books_by_testament
from bible_fetcher import fetch_book
from latex_generator import generate_book_tex, generate_testament_tex, generate_color_index_tex


def main():
    parser = argparse.ArgumentParser(
        description="Generate LaTeX files for the NET Bible"
    )
    parser.add_argument(
        "--books",
        nargs="+",
        help="Specific books to generate (by name or slug). Default: all 66.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "livres"
        ),
        help="Output directory for generated .tex files (default: livres/)",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "net_bible_cache",
        ),
        help="Cache directory for API responses (default: data/net_bible_cache/)",
    )
    args = parser.parse_args()

    # Determine which books to generate
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

    print(f"Generating {len(books_to_generate)} book(s)...")
    print(f"Output: {output_dir}")
    print(f"Cache:  {cache_dir}")
    print()

    for book in books_to_generate:
        print(f"  {book.name} ({book.chapters} chapters)...", end=" ", flush=True)

        # Fetch from API (or cache)
        chapters_data = fetch_book(book.abbreviation, book.chapters, cache_dir)

        # Generate LaTeX
        tex_content = generate_book_tex(book, chapters_data)

        # Write to file
        book_dir = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir, exist_ok=True)
        tex_path = os.path.join(book_dir, f"{book.directory}.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        print("done")

    # Generate testament include files
    print()
    print("Generating testament include files...")

    ot_books = [b for b in books_to_generate if b.testament == "OT"]
    nt_books = [b for b in books_to_generate if b.testament == "NT"]

    # Only write testament files when generating all books (or all of a testament)
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

    # Generate color index page
    index_tex = generate_color_index_tex()
    index_path = os.path.join(output_dir, "color_index.tex")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_tex)
    print("  color_index.tex written")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
