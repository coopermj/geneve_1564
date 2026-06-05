"""Tests for the two critical bugs found in code review:

  #1  ESV words-of-Christ (woc) close-tag detection was a dead branch
      (`text[i:i+6] == '</spa'` compares a 6-char slice to a 5-char string),
      so \\redletteroff was never emitted and red-letter toggles were unbalanced.

  #2  _escape_latex ran AFTER LaTeX commands were injected, so it had to skip
      backslash sequences and never escaped literal `{`, `}`, `\\` in source
      prose -- a compile-time landmine. Escaping must happen on bare prose
      BEFORE any command (\\textsc, \\vs, \\markboth, \\textit) is injected,
      and injected commands must survive intact.

Run:  python3 tests/test_latex_escaping.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import bible_config
import latex_generator as net
import esv_latex_generator as esv

GENESIS = bible_config.BOOKS[0]
assert GENESIS.directory == "genesis", GENESIS

_failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}: {detail}")
        _failures.append(name)


# ── Bug #2: NET escaping ────────────────────────────────────────────────
print("NET _escape_latex / _process_verse_text")

esc = net._escape_latex(r"a & b {x} \ y % z # _ $")
check("net escape specials",
      esc == r"a \& b \{x\} \textbackslash{} y \% z \# \_ \$",
      esc)

vt = net._process_verse_text("Trust the LORD & keep {his} word")
check("net verse escapes literal braces", r"\{his\}" in vt, vt)
# every & must be preceded by a backslash (i.e. no unescaped ampersand)
_unescaped_amp = any(c == "&" and (i == 0 or vt[i - 1] != "\\")
                     for i, c in enumerate(vt))
check("net verse escapes ampersand", r"\&" in vt and not _unescaped_amp, vt)
check("net verse injects divine name", r"\textsc{Lord}" in vt, vt)
check("net verse does NOT escape injected command braces",
      r"\textsc\{" not in vt and r"\textsc{Lord}" in vt, vt)

# argument text must be escaped before embedding in \bbook
arg = net._escape_latex("Moses & the {law} of God")
check("net argument escape", arg == r"Moses \& the \{law\} of God", arg)


# ── Bug #2: ESV footnote escaping ───────────────────────────────────────
print("ESV _clean_footnote_text")

fn = esv._clean_footnote_text("<i>Or</i> a thing {x} & y")
check("esv footnote keeps \\textit", r"\textit{Or}" in fn, fn)
check("esv footnote escapes literal brace", r"\{x\}" in fn, fn)
check("esv footnote escapes ampersand", r"\&" in fn, fn)
check("esv footnote does NOT escape \\textit braces",
      r"\textit{Or}" in fn and r"\textit\{" not in fn, fn)


# ── Bug #1 + #2: ESV chapter HTML pipeline ──────────────────────────────
print("ESV _process_chapter_html")

woc_html = (
    '<p class="p">'
    '<b class="verse-num" id="v1">1&nbsp;</b>'
    'And he said, <span class="woc">Love one another.</span> Truly.'
    '</p>'
)
out = "\n".join(esv._process_chapter_html(woc_html, 1, GENESIS, False))
on = out.count(r"\redletteron")
off = out.count(r"\redletteroff")
check("esv woc emits redletteron", on >= 1, out)
check("esv woc emits redletteroff (bug #1)", off >= 1, out)
check("esv woc toggles balanced", on == off, f"on={on} off={off} :: {out}")
check("esv emits verse marker", r"\vs{1}" in out, out)
check("esv emits markboth running header", r"\markboth{Genesis 1:1}" in out, out)

brace_html = (
    '<p class="p">'
    '<b class="verse-num">2 </b>'
    'text with {literal} brace and LORD here'
    '</p>'
)
out2 = "\n".join(esv._process_chapter_html(brace_html, 1, GENESIS, False))
check("esv prose escapes literal braces", r"\{literal\}" in out2, out2)
check("esv keeps \\vs braces unescaped", r"\vs{2}" in out2, out2)
check("esv keeps \\textsc braces unescaped", r"\textsc{Lord}" in out2, out2)


if _failures:
    print(f"\n{len(_failures)} FAILED: {_failures}")
    sys.exit(1)
print("\nAll tests passed.")
