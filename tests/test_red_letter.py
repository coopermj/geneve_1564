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

if _failures:
    print(f"\n{len(_failures)} FAILED: {_failures}")
    sys.exit(1)
print("\nAll tests passed.")
