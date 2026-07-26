"""Generate the King James Version edition book .tex files (offline from cache).

Reuses the shared generate_book_tex pipeline (headpieces, poetry, lettrines,
LORD small-caps, hyphenation) with KJV text from kjv_fetcher. No Geneva
annotations and no reading plan; red-letter is off in kjv_bible.tex (the KJV
carries no quotation marks, as in 17th-c. typography)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bible_config import BOOKS, get_books_by_testament
from latex_generator import generate_book_tex, generate_testament_tex
import kjv_fetcher

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_kjv(output_dir: str, cache_dir: str = kjv_fetcher.DEFAULT_CACHE_DIR, books=None) -> None:
    books = books or BOOKS
    print(f"[kjv] Generating {len(books)} book(s) -> {output_dir}")
    for book in books:
        chapters_data = kjv_fetcher.fetch_book(book.name, book.chapters, cache_dir)
        tex = generate_book_tex(
            book, chapters_data, plan_endpoints=None,
            annotations={}, corrections=None, note_manifest=None)
        book_dir = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir, exist_ok=True)
        with open(os.path.join(book_dir, f"{book.directory}.tex"), "w", encoding="utf-8") as f:
            f.write(tex)
    subdir = os.path.basename(output_dir)
    with open(os.path.join(output_dir, "old_testament.tex"), "w", encoding="utf-8") as f:
        f.write(generate_testament_tex(get_books_by_testament("OT"), "Old Testament", subdir=subdir))
    with open(os.path.join(output_dir, "new_testament.tex"), "w", encoding="utf-8") as f:
        f.write(generate_testament_tex(get_books_by_testament("NT"), "New Testament", subdir=subdir))
    print(f"[kjv] done -> {output_dir}")


if __name__ == "__main__":
    run_kjv(os.path.join(_ROOT, "livres_kjv"))
