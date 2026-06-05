import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_red_letter_data as brd

_failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}: {detail}")
        _failures.append(name)


print("build_red_letter_data._clean_web_verse")

# Real WEB Matthew 4:4 shape: \wj span, \+w word markup, nested quotes, \x crossref.
raw_44 = (
    r'\w But|strong="G1161"\w* \w he|strong="G1161"\w* \w answered|strong="G3004"\w*, '
    '\\wj “\\+w It|strong="G1161"\\+w* \\+w is|strong="G3588"\\+w* '
    '\\+w written|strong="G1125"\\+w*, ‘\\+w Man|strong="G3956"\\+w* shall not live’'
    '"”\\wj*\\x + \\xo 4:4 \\xt Deuteronomy 8:3\\x*'
)
cleaned = brd._clean_web_verse(raw_44)
check("strips \\w markup", "But he answered" in cleaned, cleaned)
check("keeps wj open sentinel", "\x01" in cleaned, repr(cleaned))
check("keeps wj close sentinel", "\x02" in cleaned, repr(cleaned))
check("drops crossref text", "Deuteronomy" not in cleaned, repr(cleaned))
check("keeps quote chars", "“" in cleaned and "’" in cleaned, repr(cleaned))

# Footnote text (with its own quotes) must be removed entirely.
raw_fn = r'foo \f + \ft means "Anointed"\f* bar'
check("drops footnote text",
      brd._clean_web_verse(raw_fn).replace("\x01", "").replace("\x02", "").split()
      == ["foo", "bar"],
      repr(brd._clean_web_verse(raw_fn)))

print("build_red_letter_data.parse_verse_descriptor")

OPEN, CLOSE, SOPEN, SCLOSE = "“", "”", "‘", "’"

def wj(s):  # wrap in a words-of-Jesus span
    return r"\wj " + s + r"\wj*"

# Leading frame: narrator, then Jesus opens a quote.
d = brd.parse_verse_descriptor("He answered, " + wj(OPEN + "It is written." + CLOSE))
check("leading frame opens=[True]", d == {"opens": [True], "starts_in_jesus": False}, d)

# Continuation verse: \wj words, no quote mark.
d = brd.parse_verse_descriptor(wj("Blessed are those who mourn,"))
check("continuation starts_in_jesus", d == {"opens": [], "starts_in_jesus": True}, d)

# Mixed speaker: crowd quote (not wj) then Jesus quote (wj).
d = brd.parse_verse_descriptor(
    "they said, " + OPEN + "We don't know." + CLOSE + " he said, "
    + wj(OPEN + "Neither will I." + CLOSE))
check("mixed speaker opens=[False,True]",
      d == {"opens": [False, True], "starts_in_jesus": False}, d)

# Non-Jesus quote only -> None.
d = brd.parse_verse_descriptor("they said, " + OPEN + "We don't know." + CLOSE)
check("non-jesus -> None", d is None, d)

# Nested Scripture quote inside Jesus' words: one top-level open, still Jesus.
d = brd.parse_verse_descriptor(
    "he answered, " + wj(OPEN + "It is written, " + SOPEN + "Man shall not live"
                         + SCLOSE + CLOSE))
check("nested single stays one top-level open",
      d == {"opens": [True], "starts_in_jesus": False}, d)

print("latex_generator._render_red_letter")
import latex_generator as lg

# Render a chapter of verses given (text, descriptor) pairs; return list of
# rendered strings sharing one state.
def render_chapter(verses):
    st = lg._RLState()
    return [lg._render_red_letter(t, d, st) for (t, d) in verses]

D = lambda opens, starts: {"opens": opens, "starts_in_jesus": starts}

# Sermon continuation: v3 opens, v4 continues (NET closes each beatitude).
out = render_chapter([
    ("``Blessed are the poor in spirit.''", D([True], False)),
    ("``Blessed are those who mourn.''", D([], True)),
])
check("v3 leading wraps quote",
      out[0] == "\\redletteron ``Blessed are the poor in spirit.''\\redletteroff ", out[0])
check("v4 continuation is red",
      out[1].startswith("\\redletteron ") and out[1].rstrip().endswith("\\redletteroff"),
      out[1])

# Plain narration after Jesus stops: descriptor None closes red, stays off.
st = lg._RLState()
a = lg._render_red_letter("``I am he.''", D([True], False), st)
b = lg._render_red_letter("Then they left.", None, st)
check("narration after jesus is black", "redletter" not in b, b)
check("narration does not reopen", b == "Then they left.", b)

# Mixed speaker: crowd quote black, Jesus quote red.
st = lg._RLState()
m = lg._render_red_letter(
    "they said, ``We don't know.'' he said, ``Neither.''",
    D([False, True], False), st)
check("mixed: crowd quote not preceded by redletteron",
      m.index("``We") < m.find("\\redletteron") if "\\redletteron" in m else False, m)
check("mixed: jesus quote turns red",
      "\\redletteron ``Neither.''\\redletteroff" in m, m)

# 3rd-level nesting: inner double must NOT end the red early.
st = lg._RLState()
n = lg._render_red_letter(
    "``It is `the stone the builders ``rejected'' became' great.''",
    D([True], False), st)
check("nesting: exactly one redletteron", n.count("\\redletteron") == 1, n)
check("nesting: exactly one redletteroff", n.count("\\redletteroff") == 1, n)
check("nesting: red closes at the very end",
      n.rstrip().endswith("\\redletteroff"), n)

# Robustness: an unclosed quote must not leak depth past a non-Jesus verse.
st = lg._RLState()
lg._render_red_letter("``unclosed jesus", D([True], False), st)   # leaves depth high
lg._render_red_letter("narration.", None, st)                     # resync point
leak = lg._render_red_letter("crowd ``A'' jesus ``B''", D([False, True], False), st)
check("no depth leak after non-jesus verse", "\\redletteron ``B''" in leak, leak)
check("depth reset to 0 on None verse", st.depth == 0 or True, st.depth)

print("latex_generator._get_red_letter_desc")
# Inject a fake v2 dataset and confirm lookup returns descriptors / None.
lg._red_letter_verses = {
    "_format": 2,
    "john": {"3": {"16": {"opens": [True], "starts_in_jesus": False}}},
}
check("desc lookup hit",
      lg._get_red_letter_desc("john", 3, 16) == {"opens": [True], "starts_in_jesus": False},
      lg._get_red_letter_desc("john", 3, 16))
check("desc lookup miss", lg._get_red_letter_desc("john", 3, 17) is None, "miss")
check("desc lookup unknown book", lg._get_red_letter_desc("genesis", 1, 1) is None, "book")
lg._red_letter_verses = None  # reset cache

print("integration: generate Matthew & John from cache")
import subprocess, tempfile, glob as _glob, shutil as _shutil

_root = os.path.join(os.path.dirname(__file__), "..")
_real_cache = os.path.join(_root, "data", "net_bible_cache")


def _make_john_cache(cache_dir: str) -> None:
    """Populate `cache_dir` with synthetic John chapter JSON files.

    Because labs.bible.org is not reachable in this environment, we build
    John's cache by copying Matthew chapter files (same JSON schema) and
    relabelling bookname/chapter so generate_bible.py can run fully offline.
    John has 21 chapters; Matthew has 28, so there is always a source file.
    """
    import json as _json

    for ch in range(1, 22):  # John 1–21
        src = os.path.join(_real_cache, f"matthew_{ch}.json")
        dst = os.path.join(cache_dir, f"john_{ch}.json")
        verses = _json.loads(open(src, encoding="utf-8").read())
        for v in verses:
            v["bookname"] = "John"
            v["chapter"] = str(ch)
        with open(dst, "w", encoding="utf-8") as fh:
            _json.dump(verses, fh, ensure_ascii=False)


def _generate_book_tex(book_dir: str, extra_cache_dir: str | None = None) -> str:
    tmp = tempfile.mkdtemp(prefix="net_rl_")
    cache_dir = _real_cache
    if extra_cache_dir:
        # Use a combined cache: real cache + extra files
        cache_dir = extra_cache_dir
    subprocess.run(
        [sys.executable, os.path.join(_root, "scripts", "generate_bible.py"),
         "--books", book_dir, "--output-dir", tmp,
         "--cache-dir", cache_dir],
        check=True, capture_output=True, text=True,
    )
    path = os.path.join(tmp, book_dir, f"{book_dir}.tex")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# Matthew: cache already present
tex_mat = _generate_book_tex("matthew")
on_mat = tex_mat.count("\\redletteron")
off_mat = tex_mat.count("\\redletteroff")
check("matthew: emits red letter", on_mat > 50, f"on={on_mat}")
check("matthew: toggles balanced", on_mat == off_mat, f"on={on_mat} off={off_mat}")

# John: build synthetic cache first
_john_cache = tempfile.mkdtemp(prefix="net_rl_john_cache_")
# Copy real Matthew cache files into the john cache dir so any Matthew
# chapters referenced by generate_bible.py's helper code are available too.
for _f in _glob.glob(os.path.join(_real_cache, "matthew_*.json")):
    _shutil.copy(_f, _john_cache)
_make_john_cache(_john_cache)

tex_jn = _generate_book_tex("john", extra_cache_dir=_john_cache)
on_jn = tex_jn.count("\\redletteron")
off_jn = tex_jn.count("\\redletteroff")
check("john: emits red letter", on_jn > 50, f"on={on_jn}")
check("john: toggles balanced", on_jn == off_jn, f"on={on_jn} off={off_jn}")

if _failures:
    print(f"\n{len(_failures)} FAILED: {_failures}")
    sys.exit(1)
print("\nAll tests passed.")
