#!/usr/bin/env python3
"""Genesis 1-10 sample, CAPACITY variant: smaller margin-note font (7pt) +
wider outer margin, so most notes stay in the margin and only a small residual
footnotes. Mini-converges with the anchor detector (calibrated for 7pt/wide
margin). Produces /tmp -> sample_margin_small.pdf at repo root.
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from bible_config import get_book_by_name
from bible_fetcher import fetch_book
from latex_generator import generate_book_tex
from overlap_detector import detect_from_anchors

N = 10
DOC = os.path.join(_ROOT, "sample_margin_small")
MANIFEST = os.path.join(_ROOT, "data", "sample_small_manifest.json")
ANNOT = os.path.join(_ROOT, "data", "geneva_annotations.json")
# calibrated for 7pt notes in a ~30mm margin (vs 12.3 chars/9.6pt at 9pt/narrow)
CPL, LH = 26.0, 8.4

book = get_book_by_name("genesis")
chapters = fetch_book(book.abbreviation, N, os.path.join(_ROOT, "data", "net_bible_cache"))
annotations = json.load(open(ANNOT, encoding="utf-8"))

g = open(os.path.join(_ROOT, "geneva_bible.tex"), encoding="utf-8").read()
preamble = g.split("\\begin{document}")[0]
# --- capacity overrides: wider margin + smaller note font ---
preamble = preamble.replace("\\areaset[8mm]{125mm}{210mm}", "\\areaset[8mm]{108mm}{212mm}")
preamble = preamble.replace("\\fontsize{9}{10.5}\\selectfont\\itshape",
                            "\\fontsize{7}{8.3}\\selectfont\\itshape")
preamble = preamble.replace("\\usepackage{marginnote}",
    "\\usepackage{marginnote}\\setlength\\marginparwidth{30mm}\\setlength\\marginparsep{2.5mm}")
preamble += "\\begin{document}\n"

def build_body(corr):
    manifest = []
    body = generate_book_tex(book, chapters, plan_endpoints=None,
                             annotations=annotations, corrections=corr, note_manifest=manifest)
    json.dump(manifest, open(MANIFEST, "w"))
    open(DOC + ".tex", "w", encoding="utf-8").write(preamble + body + "\n\\end{document}\n")

def compile_doc():
    env = dict(os.environ, OSFONTDIR="fonts", TEXINPUTS="microtype:")
    for _ in range(2):
        subprocess.run(["lualatex", "-shell-escape", "-interaction=nonstopmode",
                        "sample_margin_small.tex"], cwd=_ROOT, env=env, capture_output=True, text=True)

corr = {}
for it in range(1, 7):
    build_body(corr)
    compile_doc()
    new = detect_from_anchors(DOC + ".aux", MANIFEST, ANNOT,
                              already_footnoted={int(k) for k in corr},
                              chars_per_line=CPL, line_height=LH)
    print(f"iter {it}: +{len(new)} footnotes (total {len(corr)+len(new)})")
    if not new:
        print("converged"); break
    corr.update({int(k): v for k, v in new.items()})
else:
    build_body(corr); compile_doc()

total = sum(len(annotations["genesis"].get(str(c), {}).get(str(v), []))
            for c in range(1, N+1) for v in [int(x["verse"]) for x in chapters[c]])
m = re.search(r"Output written.*?\((\d+) page", open(DOC + ".log", encoding="utf-8", errors="replace").read())
print(f"pages={m.group(1) if m else '?'}  total_notes={total}  footnoted={len(corr)}  in_margin={total-len(corr)}")
