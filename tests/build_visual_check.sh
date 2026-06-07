#!/usr/bin/env bash
# Build the verse-number protrusion visual-check fixture reliably.
#
# Why this script exists:
#   The fixture loads "EB Garamond" by family name. With a RELATIVE OSFONTDIR
#   (e.g. OSFONTDIR=../fonts), luaotfload resolves that family name to a broken
#   SYSTEM EB Garamond during PDF font embedding and aborts with
#   "invalid font type (ttf)". An ABSOLUTE OSFONTDIR pointing at this repo's
#   fonts/ directory makes resolution deterministic and the build succeeds.
#   This script computes that absolute path from its own location, so it works
#   on any clone without hardcoding a machine-specific path.
#
# Usage:
#   tests/build_visual_check.sh
# Output:
#   tests/verse_protrusion_visual_check.pdf
# Then eyeball (or pixel-measure) the line-start verse number against the
# column rule: it should hang slightly into the left margin.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO/tests"

OSFONTDIR="$REPO/fonts" lualatex -interaction=nonstopmode verse_protrusion_visual_check.tex

echo "Built: $REPO/tests/verse_protrusion_visual_check.pdf"
