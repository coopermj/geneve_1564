#!/usr/bin/env python3
"""Compile net_bible.tex with iterative overlap correction for margin notes.

Usage:
    python3 scripts/build_annotated.py [--books genesis] [--max-iter 3]
    python3 scripts/build_annotated.py --books genesis exodus --max-iter 2

    # Density-prune mode (recommended for first run — prevents cascade):
    python3 scripts/build_annotated.py --density-prune [--max-iter 2]
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
from overlap_detector import detect, detect_density_excess

_MANIFEST_PATH = os.path.join(_PROJECT_ROOT, "data", "note_manifest.json")
_PDF_PATH = os.path.join(_PROJECT_ROOT, "geneva_bible.pdf")
_LUALATEX = ["lualatex", "-shell-escape", "-interaction=batchmode", "geneva_bible.tex"]
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
    parser.add_argument("--max-offset", type=float, default=0.0,
                        help="Demote to footnote when push-down exceeds this pt (default: 0 = all overlaps to footnote)")
    parser.add_argument("--density-prune", action="store_true",
                        help="Use page-density pruning: footnotes all notes that can't "
                             "physically fit on their page. Run repeatedly (--density-iter) "
                             "until no excess remains, then do --max-iter standard passes.")
    parser.add_argument("--density-iter", type=int, default=5,
                        help="Max density-prune iterations (default: 5). Stops early if "
                             "no excess found.")
    parser.add_argument("--output-dir",
                        default=os.path.join(_PROJECT_ROOT, "livres_geneva"))
    parser.add_argument("--cache-dir",
                        default=os.path.join(_PROJECT_ROOT, "data", "net_bible_cache"))
    parser.add_argument("--corrections-in",
                        help="JSON file of prior corrections to seed the run")
    parser.add_argument("--corrections-out",
                        default=os.path.join(_PROJECT_ROOT, "data", "corrections_final.json"),
                        help="Save accumulated corrections to this JSON file after run")
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
    if args.corrections_in and os.path.exists(args.corrections_in):
        with open(args.corrections_in) as f:
            raw = json.load(f)
        corrections = {int(k): v for k, v in raw.items()}
        n_fn = sum(1 for v in corrections.values() if v == "footnote")
        print(f"Loaded {len(corrections)} prior corrections ({n_fn} footnotes) from {args.corrections_in}")

    if args.density_prune:
        for d_iter in range(1, args.density_iter + 1):
            print(f"\n=== Density-prune pass {d_iter}/{args.density_iter} ===")
            print("Generating .tex files...")
            _generate(books, args.output_dir, args.cache_dir, corrections)
            _compile()
            print("Computing page density excess...", end=" ", flush=True)
            already_footnoted = {k for k, v in corrections.items() if v == "footnote"}
            density_corrections = detect_density_excess(
                _PDF_PATH, _MANIFEST_PATH, already_footnoted=already_footnoted
            )
            n_density = len(density_corrections)
            print(f"{n_density} note(s) exceed page capacity → footnote")
            if n_density == 0:
                print("No density excess — density phase complete.")
                break
            corrections.update(density_corrections)

    for iteration in range(1, args.max_iter + 1):
        print(f"\n=== Iteration {iteration}/{args.max_iter} ===")

        print("Generating .tex files...")
        _generate(books, args.output_dir, args.cache_dir, corrections)

        _compile()

        print("Detecting overlaps...", end=" ", flush=True)
        already_footnoted = {k for k, v in corrections.items() if v == "footnote"}
        new_corrections = detect(_PDF_PATH, _MANIFEST_PATH, max_offset=args.max_offset,
                                 already_footnoted=already_footnoted)

        if not new_corrections:
            print(f"none found.")
            print(f"\nDone — no overlaps after {iteration} iteration(s).")
            if args.corrections_out:
                os.makedirs(os.path.dirname(args.corrections_out), exist_ok=True)
                with open(args.corrections_out, "w") as f:
                    json.dump({str(k): v for k, v in corrections.items()}, f)
                print(f"Saved {len(corrections)} corrections to {args.corrections_out}")
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

    if args.corrections_out:
        os.makedirs(os.path.dirname(args.corrections_out), exist_ok=True)
        with open(args.corrections_out, "w") as f:
            json.dump({str(k): v for k, v in corrections.items()}, f)
        print(f"Saved {len(corrections)} corrections to {args.corrections_out}")

    print(f"\nDone — {args.max_iter} iteration(s) completed.")


if __name__ == "__main__":
    main()
