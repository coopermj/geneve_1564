#!/usr/bin/env python3
"""Build a layout SAMPLE: Genesis 1-10 with Geneva annotations rendered as
end-of-chapter notes (no margin notes -> no overlap, every note shown).

Writes /tmp/sample_genesis.tex (a standalone document). Offline from cache.
This is a throwaway prototype for evaluating the redesign, not production.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from bible_config import get_book_by_name
from bible_fetcher import fetch_book
from latex_generator import (
    _process_verse_text, _RLState, _render_red_letter, _get_red_letter_desc,
    _convert_smart_quotes, _escape_latex,
)

N_CHAPTERS = 10
book = get_book_by_name("genesis")
chapters = fetch_book(book.abbreviation, N_CHAPTERS,
                      os.path.join(_ROOT, "data", "net_bible_cache"))
ann = json.load(open(os.path.join(_ROOT, "data", "geneva_annotations.json"),
                     encoding="utf-8")).get("genesis", {})

PREAMBLE = r"""\documentclass[twocolumn,paper=179mm:239mm,pagesize=auto,fontsize=11pt,oneside]{scrbook}
\areaset[12mm]{150mm}{210mm}
\usepackage{fontspec}
\setmainfont{EB Garamond}[Path=fonts/,Extension=.otf,
  UprightFont=EBGaramond-Regular, ItalicFont=EBGaramond-Italic,
  BoldFont=EBGaramond-Bold, BoldItalicFont=EBGaramond-BoldItalic]
\usepackage[protrusion=true,expansion=true,final]{microtype}
\usepackage{scripture}
\scripturesetup{
  chapter/drop=false, chapter/para=true,
  chapter/font=\scshape, chapter/format=Chapter~#1,
  chapter/para/aboveskip=\baselineskip, chapter/para/belowskip=0pt,
  verse/format=\textsuperscript{#1}, verse/sep=0.1em, verse/first=false,
  indent=true,
}
% End-of-chapter Geneva annotation marker + notes block
\newcommand{\gva}[1]{\textsuperscript{\itshape #1}}
\newcommand{\chapternotes}[1]{%
  \par\nobreak\vspace{4pt}%
  {\centering\rule{0.4\linewidth}{0.3pt}\par}%
  \vspace{2pt}%
  \begingroup\footnotesize\setlength{\parindent}{0pt}%
  #1\par\endgroup\vspace{2pt}}
\newcommand{\gvanote}[2]{\textsuperscript{\itshape #1}\,\textit{#2}\quad}
\begin{document}
\begin{scripture}
"""

lines = [PREAMBLE]
for ch in range(1, N_CHAPTERS + 1):
    verses = chapters[ch]
    rl = _RLState()
    lines.append("")
    lines.append(f"\\ch{{{ch}}} %")
    notes = []
    for v in verses:
        vn = int(v["verse"])
        text = _process_verse_text(v["text"])
        desc = _get_red_letter_desc("genesis", ch, vn)
        text = _render_red_letter(text, desc, rl)
        vnotes = ann.get(str(ch), {}).get(str(vn), [])
        suffix = ""
        for n in vnotes:
            suffix += f"\\gva{{{n['letter']}}}"
            notes.append((n["letter"], _escape_latex(_convert_smart_quotes(n["text"]))))
        if vn == 1:
            lines.append(f"{text}{suffix}")
        else:
            lines.append(f"\\vs{{{vn}}} {text}{suffix}")
    if notes:
        body = "".join(f"\\gvanote{{{l}}}{{{t}}}" for l, t in notes)
        lines.append(f"\\chapternotes{{{body}}}")

lines.append("\\end{scripture}")
lines.append("\\end{document}")

out = os.path.join("/tmp", "sample_genesis.tex")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"wrote {out}  ({sum(len(ann.get(str(c),{}).get(str(v),[])) for c in range(1,N_CHAPTERS+1) for v in [int(x['verse']) for x in chapters[c]])} annotations across {N_CHAPTERS} chapters)")
