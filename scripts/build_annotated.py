#!/usr/bin/env python3
"""Compile net_bible.tex with iterative overlap correction for margin notes.

Usage:
    python3 scripts/build_annotated.py [--books genesis] [--max-iter 3]
    python3 scripts/build_annotated.py --books genesis exodus --max-iter 2
"""

import argparse
import json
import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)

from bible_config import BOOKS, get_book_by_name
from bible_fetcher import fetch_book
from latex_generator import generate_book_tex
from overlap_detector import detect

_MANIFEST_PATH = os.path.join(_PROJECT_ROOT, "data", "note_manifest.json")
_PDF_PATH = os.path.join(_PROJECT_ROOT, "net_bible.pdf")
_LUALATEX = ["lualatex", "-shell-escape", "-interaction=batchmode", "net_bible.tex"]
_ENV = {**os.environ, "OSFONTDIR": "fonts", "TEXINPUTS": "microtype:"}


def _compile():
    print("  Compiling (pass 1)...", end=" ", flush=True)
    r1 = subprocess.run(_LUALATEX, cwd=_PROJECT_ROOT, env=_ENV,
                        capture_output=True, text=True)
    if r1.returncode != 0:
        print("FAILED")
        print(r1.stdout[-3000:])
        sys.exit(1)
    print("ok")
    print("  Compiling (pass 2)...", end=" ", flush=True)
    r2 = subprocess.run(_LUALATEX, cwd=_PROJECT_ROOT, env=_ENV,
                        capture_output=True, text=True)
    if r2.returncode != 0:
        print("FAILED")
        print(r2.stdout[-3000:])
        sys.exit(1)
    print("ok")


def _generate(books, output_dir, cache_dir, corrections):
    note_manifest: list = []
    for book in books:
        chapters_data = fetch_book(book.abbreviation, book.chapters, cache_dir)
        tex_content = generate_book_tex(
            book, chapters_data,
            note_manifest=note_manifest,
            corrections=corrections if corrections else None,
        )
        book_dir_path = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir_path, exist_ok=True)
        with open(os.path.join(book_dir_path, f"{book.directory}.tex"), "w",
                  encoding="utf-8") as f:
            f.write(tex_content)

    os.makedirs(os.path.dirname(_MANIFEST_PATH), exist_ok=True)
    with open(_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(note_manifest, f)
    print(f"  Generated {len(books)} book(s), {len(note_manifest)} annotation notes")
    return note_manifest


def main():
    parser = argparse.ArgumentParser(
        description="Compile NET Bible with iterative margin note overlap correction"
    )
    parser.add_argument("--books", nargs="+",
                        help="Books to process (name or slug). Default: all 66.")
    parser.add_argument("--max-iter", type=int, default=3,
                        help="Maximum correction iterations (default: 3)")
    parser.add_argument("--output-dir",
                        default=os.path.join(_PROJECT_ROOT, "livres"))
    parser.add_argument("--cache-dir",
                        default=os.path.join(_PROJECT_ROOT, "data", "net_bible_cache"))
    args = parser.parse_args()

    if args.books:
        books = []
        for name in args.books:
            b = get_book_by_name(name)
            if b is None:
                print(f"Error: unknown book '{name}'", file=sys.stderr)
                sys.exit(1)
            books.append(b)
    else:
        books = BOOKS

    corrections: dict = {}

    for iteration in range(1, args.max_iter + 1):
        print(f"\n=== Iteration {iteration}/{args.max_iter} ===")

        print("Generating .tex files...")
        _generate(books, args.output_dir, args.cache_dir, corrections)

        _compile()

        print("Detecting overlaps...", end=" ", flush=True)
        new_corrections = detect(_PDF_PATH, _MANIFEST_PATH)

        if not new_corrections:
            print(f"none found.")
            print(f"\nDone — no overlaps after {iteration} iteration(s).")
            return

        n_offsets = sum(1 for v in new_corrections.values() if v != "footnote")
        n_footnotes = sum(1 for v in new_corrections.values() if v == "footnote")
        print(f"{n_offsets} offset(s), {n_footnotes} footnote demotion(s)")

        corrections.update(new_corrections)

    # Reached max iterations — apply all accumulated corrections in a final pass
    print(f"\n=== Final pass (corrections applied) ===")
    print("Generating .tex files with all corrections...")
    _generate(books, args.output_dir, args.cache_dir, corrections)
    _compile()
    print(f"\nDone — {args.max_iter} iteration(s) completed.")


if __name__ == "__main__":
    main()
