#!/usr/bin/env python3
"""Build a visual sample of the new per-line poetry emission.

Generates four short poetry sections from cache (no network, no annotations)
and compiles them to sample_poetry.pdf at repo root.  Then prints x-position
statistics and saves first-page PNGs for each book section.

Usage: python3 scripts/sample_poetry.py
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = os.path.join(_ROOT, "data", "net_bible_cache")

from bible_config import get_book_by_name
from bible_fetcher import fetch_chapter
from latex_generator import generate_book_tex


def _load_chapter(abbrev: str, ch: int) -> list:
    """Load a single chapter from cache (no network)."""
    safe = abbrev.replace(" ", "_").lower()
    path = os.path.join(_CACHE, f"{safe}_{ch}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Unwrap if wrapped in single-quote string (API quirk)
    if isinstance(data, str):
        data = json.loads(data.strip("'"))
    return data


def _book_body(book_name: str, chapters: dict[int, list]) -> str:
    """Generate LaTeX body for one book (no annotations)."""
    book = get_book_by_name(book_name)
    return generate_book_tex(book, chapters,
                             plan_endpoints=None,
                             annotations={},
                             corrections=None,
                             note_manifest=None)


# ── Load chapters from cache ────────────────────────────────────────────────
isa = get_book_by_name("isaiah")
psa = get_book_by_name("psalms")
lam = get_book_by_name("lamentations")
sos = get_book_by_name("songofsolomon")

isa_ch56  = _load_chapter(isa.abbreviation, 56)
psa_ch101 = _load_chapter(psa.abbreviation, 101)
psa_ch23  = _load_chapter(psa.abbreviation, 23)
lam_ch1   = _load_chapter(lam.abbreviation, 1)
sos_ch1   = _load_chapter(sos.abbreviation, 1)

bodies = []
bodies.append(_book_body("isaiah",       {56: isa_ch56}))
bodies.append(_book_body("psalms",       {101: psa_ch101, 23: psa_ch23}))
bodies.append(_book_body("lamentations", {1: lam_ch1}))
bodies.append(_book_body("songofsolomon", {1: sos_ch1}))

# ── Preamble from geneva_bible.tex ──────────────────────────────────────────
gtex = open(os.path.join(_ROOT, "geneva_bible.tex"), encoding="utf-8").read()
preamble = gtex.split("\\begin{document}")[0] + "\\begin{document}\n"

doc = "\n\n".join(bodies)
full = preamble + doc + "\n\\end{document}\n"

out_stem = os.path.join(_ROOT, "sample_poetry")
with open(out_stem + ".tex", "w", encoding="utf-8") as f:
    f.write(full)

# ── Compile twice ────────────────────────────────────────────────────────────
env = dict(os.environ, OSFONTDIR="fonts")
for i in range(2):
    r = subprocess.run(
        ["lualatex", "-interaction=nonstopmode", "sample_poetry.tex"],
        cwd=_ROOT, env=env, capture_output=True, text=True
    )
    print(f"pass {i+1}: returncode={r.returncode}")

# ── Log summary ──────────────────────────────────────────────────────────────
log = open(out_stem + ".log", encoding="utf-8", errors="replace").read()
import re
m = re.search(r"Output written.*?\((\d+) page", log)
print("pages:", m.group(1) if m else "?")

# ── X-position analysis ──────────────────────────────────────────────────────
import fitz
doc_pdf = fitz.open(out_stem + ".pdf")
xs: dict[int, int] = {}
for page in doc_pdf:
    for b in page.get_text("dict")["blocks"]:
        for l in b["lines"]:
            x = round(l["bbox"][0])
            xs[x] = xs.get(x, 0) + 1
print("x-position clusters (x: count):", sorted(xs.items()))

# ── First-page PNGs ──────────────────────────────────────────────────────────
for n in range(min(6, len(doc_pdf))):
    page = doc_pdf[n]
    page.get_pixmap(dpi=150).save(os.path.join(_ROOT, f"sample_poetry_p{n+1}.png"))
    print(f"saved sample_poetry_p{n+1}.png")

doc_pdf.close()
print("done.")
