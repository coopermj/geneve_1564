#!/usr/bin/env python3
"""Build a SAMPLE of the real geneva MARGIN layout for Genesis 1-10 with
overlaps fixed: generate margin notes, compile to capture anchors, run the
accurate anchor-based detector to footnote the residual overlaps, regenerate,
recompile. Produces /tmp/sample_margin.pdf (clean margins, same look).

Usage: python3 scripts/sample_margin.py
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from bible_config import get_book_by_name
from bible_fetcher import fetch_book
from latex_generator import generate_book_tex
from overlap_detector import detect_from_anchors

N = 10
DOC = os.path.join(_ROOT, "sample_margin")           # stem (in repo root for fonts/)
MANIFEST = os.path.join(_ROOT, "data", "sample_margin_manifest.json")
ANNOT = os.path.join(_ROOT, "data", "geneva_annotations.json")

book = get_book_by_name("genesis")
chapters = fetch_book(book.abbreviation, N, os.path.join(_ROOT, "data", "net_bible_cache"))
annotations = json.load(open(ANNOT, encoding="utf-8"))

# geneva preamble: everything up to and including \begin{document}
gtex = open(os.path.join(_ROOT, "geneva_bible.tex"), encoding="utf-8").read()
preamble = gtex.split("\\begin{document}")[0] + "\\begin{document}\n"

def build_body(corrections):
    manifest = []
    body = generate_book_tex(book, chapters, plan_endpoints=None,
                             annotations=annotations, corrections=corrections,
                             note_manifest=manifest)
    json.dump(manifest, open(MANIFEST, "w"))
    with open(DOC + ".tex", "w", encoding="utf-8") as f:
        f.write(preamble + body + "\n\\end{document}\n")

def compile_doc():
    env = dict(os.environ, OSFONTDIR="fonts", TEXINPUTS="microtype:")
    for _ in range(2):
        subprocess.run(["lualatex", "-shell-escape", "-interaction=nonstopmode",
                        "sample_margin.tex"], cwd=_ROOT, env=env,
                       capture_output=True, text=True)

corrections = {}
for it in range(1, 6):
    build_body(corrections)
    compile_doc()
    new = detect_from_anchors(DOC + ".aux", MANIFEST, ANNOT,
                              already_footnoted={int(k) for k in corrections})
    print(f"iter {it}: new footnote demotions = {len(new)} (total {len(corrections)+len(new)})")
    if not new:
        print("converged: 0 residual overlaps")
        break
    corrections.update({int(k): v for k, v in new.items()})
else:
    build_body(corrections); compile_doc()

# report
log = open(DOC + ".log", encoding="utf-8", errors="replace").read()
m = re.search(r"Output written.*?\((\d+) page", log)
print("pages:", m.group(1) if m else "?")
print("total margin notes:", sum(len(annotations["genesis"].get(str(c), {}).get(str(v), []))
        for c in range(1, N+1) for v in [int(x["verse"]) for x in chapters[c]]))
print("footnoted (residual):", len(corrections))
