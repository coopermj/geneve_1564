#!/usr/bin/env python3
"""Generate LaTeX .tex files for the NET Bible using the scripture package.

Usage:
    python3 scripts/generate_bible.py                    # Generate all 66 books
    python3 scripts/generate_bible.py --books genesis     # Generate specific books
    python3 scripts/generate_bible.py --books genesis exodus psalms
    python3 scripts/generate_bible.py --start-date 2026-03-02
"""

import argparse
import json
import os
import sys

# Ensure the scripts directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bible_config import BOOKS, get_book_by_name, get_books_by_testament
from bible_fetcher import fetch_book
from latex_generator import (
    generate_book_tex,
    generate_testament_tex,
    generate_reading_plan_tex,
)
from reading_plan_parser import (
    extract_entries_from_pdf,
    schedule_plan,
    build_plan_endpoints,
)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_PDF_PATH = os.path.join(
    _PROJECT_ROOT, "2-Year-Bible-Reading-Plan_LisaNotes.com_.pdf"
)
_JSON_PATH = os.path.join(_SCRIPT_DIR, "reading_plan.json")


def _load_or_parse_plan():
    """Load reading plan entries from cached JSON, or parse the PDF."""
    if os.path.isfile(_JSON_PATH):
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    print("Parsing reading plan PDF...")
    entries = extract_entries_from_pdf(_PDF_PATH)
    with open(_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    print(f"  {len(entries)} entries cached to {_JSON_PATH}")
    return entries


def run_net(output_dir: str, cache_dir: str, books=None,
            annotated: bool = False, corrections_path: str | None = None,
            start_date: str = "2026-03-02", plan_markers: bool = True) -> None:
    """Generate NET book .tex (plain or annotated) + testament + reading plan into output_dir."""
    from datetime import date as date_cls
    books_to_generate = books if books else BOOKS
    plan_entries = _load_or_parse_plan()
    scheduled = schedule_plan(plan_entries, date_cls.fromisoformat(start_date))
    plan_endpoints = build_plan_endpoints(scheduled)
    book_plan_endpoints = plan_endpoints if plan_markers else None

    annotations: dict | None = {}  # empty dict = no annotations (avoids auto-load)
    corrections = None
    # generate_book_tex appends note records to this list in-place
    note_manifest = None
    if annotated:
        with open(os.path.join(_PROJECT_ROOT, "data", "geneva_annotations.json"), encoding="utf-8") as _af:
            annotations = json.load(_af)
        if corrections_path and os.path.exists(corrections_path):
            with open(corrections_path, encoding="utf-8") as _cf:
                raw = json.load(_cf)
            corrections = {int(k): v for k, v in raw.items()}
        note_manifest = []

    label = "geneva" if annotated else "net"
    print(f"[{label}] Generating {len(books_to_generate)} book(s) -> {output_dir}")
    for book in books_to_generate:
        chapters_data = fetch_book(book.abbreviation, book.chapters, cache_dir)
        tex_content = generate_book_tex(
            book, chapters_data, plan_endpoints=book_plan_endpoints,
            annotations=annotations, corrections=corrections, note_manifest=note_manifest)
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
    with open(os.path.join(output_dir, "reading_plan.tex"), "w", encoding="utf-8") as f:
        f.write(generate_reading_plan_tex(scheduled))
    if note_manifest is not None:
        with open(os.path.join(_PROJECT_ROOT, "data", "note_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(note_manifest, f)


def main():
    parser = argparse.ArgumentParser(description="Generate LaTeX files for the NET Bible")
    parser.add_argument("--books", nargs="+")
    parser.add_argument("--output-dir", default=os.path.join(_PROJECT_ROOT, "livres_net"))
    parser.add_argument("--cache-dir", default=os.path.join(_PROJECT_ROOT, "data", "net_bible_cache"))
    parser.add_argument("--start-date", default="2026-03-02")
    args = parser.parse_args()
    books = [get_book_by_name(n) for n in args.books] if args.books else None
    if books and any(b is None for b in books):
        print("Error: unknown book", file=sys.stderr); sys.exit(1)
    run_net(args.output_dir, args.cache_dir, books, start_date=args.start_date)
    print("Done!")


if __name__ == "__main__":
    main()
