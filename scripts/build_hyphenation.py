#!/usr/bin/env python3
"""Build the biblical proper-name \\hyphenation exceptions for line_breaking.tex.

Sources (both published Bible-typesetting authorities), intersected with the
proper nouns that actually occur in the ESV/NET generated text so we only ship
break points for words that appear:

  - Scribe's Bible hyphenation list (scribenet.com) — primary
  - Potts, *A Dictionary of Bible Proper Names* (1922, public domain, archive.org)
    — gap fill. Potts is OCR'd (accented vowels are garbled), so it is used ONLY
    for break POSITIONS, which are applied to our clean spelling and validated
    (de-hyphenated form must equal the text token).

The value is break-position CORRECTNESS: TeX's default English patterns break
Hebrew names wrongly (Bels-haz-zar) or not at all (Melchizedek).

Usage:
    python3 scripts/build_hyphenation.py            # rewrite the block in-place
    python3 scripts/build_hyphenation.py --check     # regenerate and diff only

Sources are cached under data/hyphenation_cache/ (gitignored); pass --offline to
require the cache. Re-run whenever the edition text changes.
"""
import argparse
import html
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = os.path.join(_ROOT, "data", "hyphenation_cache")
_LB = os.path.join(_ROOT, "line_breaking.tex")
_TEXT_DIRS = ["livres_esv", "livres_net"]
_MIN_LEN = 6

SCRIBE_URL = "https://scribenet.com/wfdw/docs/resources/bible-hyphenation.html"
POTTS_URL = ("https://archive.org/download/dictionaryofbibl00pott/"
             "dictionaryofbibl00pott_djvu.txt")

BEGIN = "% BEGIN generated hyphenation (scripts/build_hyphenation.py)"
END = "% END generated hyphenation"

# Consistent OCR substitutions for accented vowels in the Potts scan.
_POTTS_JUNK = str.maketrans({"&": "a", "S": "e", "Q": "o", "§": "e"})


def _cached(name, url, offline):
    os.makedirs(_CACHE, exist_ok=True)
    path = os.path.join(_CACHE, name)
    if not os.path.exists(path):
        if offline:
            sys.exit(f"missing cache {path} and --offline set")
        import requests
        print(f"fetching {url}")
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        with open(path, "w", encoding="utf-8") as f:
            f.write(r.text)
    return open(path, encoding="utf-8", errors="replace").read()


def parse_scribe(html_text):
    """Return {Name: 'hy-phen-ation'} from Scribe's HTML table."""
    out = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html_text, re.S | re.I):
        nm = re.search(r"<strong>\s*(.*?)\s*</strong>", row, re.S | re.I)
        if not nm:
            continue
        name = html.unescape(re.sub(r"<[^>]+>", "", nm.group(1))).strip()
        if not re.fullmatch(r"[A-Za-z’'.\- ]+", name or ""):
            continue
        for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I):
            c = html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            if c and c.lower() != name.lower() and re.fullmatch(r"[A-Za-z’'\-]+", c):
                if "-" in c:
                    out[name] = c
                break
    return out


def parse_potts(txt):
    """Return {clean_lower_spelling: [syllables]} from the OCR dictionary."""
    ent = re.compile(r"^([A-Z][A-Za-z'&.\- ]{1,28}?)\.\s+[HG]\.\s*\d")
    out = {}
    for line in txt.split("\n"):
        m = ent.match(line)
        if not m:
            continue
        parts = [p for p in re.split(r"[’'`\-\s]+", m.group(1)) if p]
        syls = [re.sub(r"[^A-Za-z&S§Q]", "", p).translate(_POTTS_JUNK) for p in parts]
        syls = [s for s in syls if s]
        if len(syls) < 2:
            continue
        out.setdefault("".join(syls).lower(), syls)
    return out


def text_tokens(root):
    """Distinct capitalized tokens (len>=MIN_LEN) in the edition text."""
    toks = set()
    for d in _TEXT_DIRS:
        base = os.path.join(root, d)
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".tex"):
                    continue
                s = open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace").read()
                s = re.sub(r"\\[A-Za-z@]+\*?", "", s).replace("{", " ").replace("}", " ")
                for w in re.findall(r"[A-Z][a-zA-Z]+", s):
                    if len(w) >= _MIN_LEN:
                        toks.add(w)
    return toks


def potts_break(name, potts):
    syls = potts.get(name.lower())
    if not syls or sum(len(s) for s in syls) != len(name):
        return None
    out, i = [], 0
    for s in syls:
        out.append(name[i:i + len(s)])
        i += len(s)
    cand = "-".join(out)
    return cand if cand.replace("-", "") == name else None


def build(scribe, potts, tokens):
    final = {}
    for w in tokens:
        hy = None
        if w in scribe:
            hy = scribe[w]
        elif potts_break(w, potts):
            hy = potts_break(w, potts)
        elif w.endswith("s") and len(w) > 4:               # plural -> singular
            sing = w[:-1]
            if sing in scribe:
                hy = scribe[sing] + "s"
            elif potts_break(sing, potts):
                hy = potts_break(sing, potts) + "s"
        if hy and "-" in hy and hy.replace("-", "") == w:  # validate
            final[w] = hy
    return final


def format_block(final):
    items = sorted(final.values(), key=str.lower)
    rows = ["  " + " ".join(items[i:i + 6]) for i in range(0, len(items), 6)]
    return "\\hyphenation{\n" + "\n".join(rows) + "\n}"


def splice(block):
    s = open(_LB, encoding="utf-8").read()
    new, n = re.subn(re.escape(BEGIN) + r".*?" + re.escape(END),
                     lambda _m: BEGIN + "\n" + block + "\n" + END, s, count=1, flags=re.S)
    if n == 0:
        sys.exit("marker block not found in line_breaking.tex "
                 f"({BEGIN!r} ... {END!r})")
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="diff only, do not write")
    ap.add_argument("--offline", action="store_true", help="require cached sources")
    args = ap.parse_args()

    scribe = parse_scribe(_cached("scribe.html", SCRIBE_URL, args.offline))
    scribe = {k: v for k, v in scribe.items() if v}
    potts = parse_potts(_cached("potts.txt", POTTS_URL, args.offline))
    tokens = text_tokens(_ROOT)
    final = build(scribe, potts, tokens)
    print(f"scribe={len(scribe)} potts={len(potts)} text-names={len(tokens)} "
          f"-> {len(final)} hyphenation entries")

    block = format_block(final)
    new = splice(block)
    cur = open(_LB, encoding="utf-8").read()
    if new == cur:
        print("line_breaking.tex already up to date.")
    elif args.check:
        print("DIFFERS from committed block (run without --check to rewrite).")
        sys.exit(1)
    else:
        with open(_LB, "w", encoding="utf-8") as f:
            f.write(new)
        print("rewrote hyphenation block in line_breaking.tex")


if __name__ == "__main__":
    main()
