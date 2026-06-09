"""Detect overlapping margin notes in a compiled PDF using PyMuPDF."""

import json
import math
import os
import re

import fitz  # PyMuPDF

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

GAP = 2.0
BOTTOM_MARGIN = 36.0

# All margin notes go to the outer (right) margin only.
# \@mn@margintest has been patched to always return \@tempswatrue so that
# left-column text no longer sends notes to the inner (binding) margin.
# The right-margin threshold: blocks whose left edge > 0.86 * page_width.


def _identify_margin_notes(blocks: list, margin_x: float) -> tuple[list, list]:
    """Return (left_blocks, right_blocks) for the outer margin zone.

    With the marginnote patch in net_bible.tex, ALL notes appear in the
    outer (right) margin regardless of column.  left_blocks is always
    empty; right_blocks contains all margin-note blocks sorted top-to-bottom.
    The two-element return keeps the call-sites unchanged.
    """
    right = sorted(
        [b for b in blocks if b["bbox"][0] > margin_x],
        key=lambda b: b["bbox"][1],
    )
    return [], right


def detect_overlaps_from_rects(
    rects: list[tuple],
    gap: float = GAP,
    page_height: float = 677.0,
    bottom_margin: float = BOTTOM_MARGIN,
    max_offset: float | None = None,
) -> dict:
    """Detect overlapping bounding boxes and compute push-down corrections.

    Args:
        rects: List of (x0, y0, x1, y1) tuples, sorted by y0.
        gap: Minimum gap in points between notes.
        page_height: Page height in points.
        bottom_margin: Notes pushed past (page_height - bottom_margin) → footnote.
        max_offset: Demote to footnote when cumulative push-down exceeds this
            value (points). None = no limit (old behaviour).

    Returns:
        {note_index: offset_pt | "footnote"} — only indices needing correction.
    """
    corrections = {}
    adjusted = list(rects)

    for i in range(len(adjusted) - 1):
        x0_i, y0_i, x1_i, y1_i = adjusted[i]
        x0_j, y0_j, x1_j, y1_j = adjusted[i + 1]

        if y1_i + gap > y0_j:
            push = (y1_i + gap) - y0_j
            new_y0 = y0_j + push
            new_y1 = y1_j + push
            adjusted[i + 1] = (x0_j, new_y0, x1_j, new_y1)

            prev = corrections.get(i + 1, 0)
            if prev == "footnote":
                continue
            total = (prev + push) if isinstance(prev, (int, float)) else push

            if new_y1 > page_height - bottom_margin:
                corrections[i + 1] = "footnote"
            elif max_offset is not None and total > max_offset:
                corrections[i + 1] = "footnote"
            else:
                corrections[i + 1] = total

    return corrections


def detect_density_excess(
    pdf_path: str,
    manifest_path: str,
    already_footnoted: set | None = None,
    gap: float = GAP,
    bottom_margin: float = BOTTOM_MARGIN,
) -> dict:
    """Footnote ALL notes that cannot physically fit on their page column.

    Unlike the iterative detect(), which flags one overlap at a time and
    causes a cascade, this function simulates stacking each page's notes
    sequentially and footnotes every note beyond the page capacity in a
    single pass.  Running this once (or twice) converges far more quickly.

    Args:
        already_footnoted: Manifest indices already demoted; skipped when
            matching PDF margin blocks to the manifest.

    Returns:
        {manifest_idx: "footnote"} for every note that cannot fit.
    """
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    if not manifest:
        return {}

    footnoted = already_footnoted or set()
    margin_manifest = [e for e in manifest if e["idx"] not in footnoted]

    def _column_fits(rects: list[tuple]) -> int:
        """Return how many notes from this column fit without overflow."""
        count = 0
        current_bottom = 0.0
        for i, (x0, y0, x1, y1) in enumerate(rects):
            note_height = y1 - y0
            start = y0 if i == 0 else max(y0, current_bottom + gap)
            end = start + note_height
            if end <= usable_bottom:
                count += 1
                current_bottom = end
            else:
                break
        return count

    doc = fitz.open(pdf_path)
    all_corrections: dict = {}
    global_note_idx = 0

    for page in doc:
        page_width = page.rect.width
        page_height = page.rect.height
        margin_x = page_width * 0.86
        usable_bottom = page_height - bottom_margin

        raw_blocks = page.get_text("dict")["blocks"]
        text_blocks = [
            {
                "bbox": b["bbox"],
                "text": " ".join(
                    span["text"]
                    for line in b.get("lines", [])
                    for span in line.get("spans", [])
                ),
            }
            for b in raw_blocks
            if b["type"] == 0
        ]
        left_blocks, right_blocks = _identify_margin_notes(text_blocks, margin_x=margin_x)

        # Process each column independently: left column notes come first
        # in the manifest sequence, then right column notes.
        for col_blocks in (left_blocks, right_blocks):
            rects = [b["bbox"] for b in col_blocks]
            fits = _column_fits(rects)
            for local_i in range(len(rects)):
                if global_note_idx >= len(margin_manifest):
                    break
                if local_i >= fits:
                    manifest_idx = margin_manifest[global_note_idx]["idx"]
                    all_corrections[manifest_idx] = "footnote"
                global_note_idx += 1

    doc.close()
    return all_corrections


def _match_blocks_to_manifest(
    pdf_blocks: list,
    manifest_entries: list,
) -> dict:
    """Match PDF margin-note blocks to manifest entries by content fingerprint.

    Each manifest entry has a ``text_prefix`` field (first 20 chars of plain
    note text) and a ``letter`` field.  Each PDF block starts with the letter
    followed by a space then the note text.  We match greedily: for each
    manifest entry (in document order) we find the first unmatched block whose
    text contains the entry's letter and text_prefix, consuming it.

    Returns {manifest_idx: block_index_in_pdf_blocks} for matched entries.
    Falls back to sequential matching for entries without ``text_prefix``.
    """
    used = set()
    result: dict = {}

    for entry in manifest_entries:
        letter = entry["letter"]
        prefix = entry.get("text_prefix", "")

        best = None
        for i, blk in enumerate(pdf_blocks):
            if i in used:
                continue
            txt = blk["text"]
            # Block text starts with the letter marker then the note body
            starts_ok = txt.startswith(letter) and (
                len(txt) <= len(letter) or not txt[len(letter)].isalpha()
            )
            if not starts_ok:
                continue
            if prefix and prefix[:10].lower() not in txt.lower():
                continue
            best = i
            break

        if best is None:
            # Fall back: take first unused block (sequential)
            for i in range(len(pdf_blocks)):
                if i not in used:
                    best = i
                    break

        if best is not None:
            result[entry["idx"]] = best
            used.add(best)

    return result


def _parse_aux_page_assignments(aux_path: str) -> list[int]:
    """Parse the LaTeX aux file for marginnote page assignments.

    Returns a list of absolute page numbers (1-based), one per \newmarginnote
    entry in the aux file, in the order they appear.  Entry K in this list
    gives the PDF page for the Kth margin note in document order.
    """
    pages: list[int] = []
    pattern = re.compile(r"\\newmarginnote\{[^}]+\}\{\{(\d+)\}")
    try:
        with open(aux_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = pattern.search(line)
                if m:
                    pages.append(int(m.group(1)))
    except FileNotFoundError:
        pass
    return pages


def detect(
    pdf_path: str,
    manifest_path: str,
    max_offset: float | None = None,
    already_footnoted: set | None = None,
) -> dict:
    """Detect overlapping margin notes in a compiled PDF.

    Uses the LaTeX aux file (same stem as pdf_path) for accurate page
    assignments, then content-fingerprint matching within each page.

    Args:
        already_footnoted: Set of manifest idx values already demoted to
            footnotes.  These are skipped so the aux-file index sequence
            stays aligned with the remaining margin notes.
    """
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    if not manifest:
        return {}

    footnoted = already_footnoted or set()
    # margin_manifest: notes still in the margin (in document order)
    margin_manifest = [e for e in manifest if e["idx"] not in footnoted]

    # Read aux file page assignments (one per \newmarginnote, document order)
    aux_path = os.path.splitext(pdf_path)[0] + ".aux"
    aux_pages = _parse_aux_page_assignments(aux_path)

    # Build per-PDF-page list of manifest entries using aux assignments.
    # aux_pages has one entry per non-footnoted \marginnote in document order,
    # matching margin_manifest entry-for-entry: aux_pages[K] is the PDF page
    # for margin_manifest[K].
    page_to_entries: dict[int, list] = {}
    for k, entry in enumerate(margin_manifest):
        if k >= len(aux_pages):
            break
        pdf_page = aux_pages[k]
        page_to_entries.setdefault(pdf_page, []).append(entry)

    doc = fitz.open(pdf_path)
    all_corrections: dict = {}

    for page in doc:
        pdf_page_1based = page.number + 1
        page_entries = page_to_entries.get(pdf_page_1based, [])

        page_width = page.rect.width
        page_height = page.rect.height
        margin_x = page_width * 0.86

        raw_blocks = page.get_text("dict")["blocks"]
        text_blocks = [
            {
                "bbox": b["bbox"],
                "text": " ".join(
                    span["text"]
                    for line in b.get("lines", [])
                    for span in line.get("spans", [])
                ),
            }
            for b in raw_blocks
            if b["type"] == 0
        ]
        _, right_blocks = _identify_margin_notes(text_blocks, margin_x=margin_x)

        if not right_blocks:
            continue

        # Match manifest entries to PDF blocks by content fingerprint
        idx_to_block = _match_blocks_to_manifest(right_blocks, page_entries)

        # Detect geometric overlaps in PDF y-order
        rects = [b["bbox"] for b in right_blocks]
        block_corrections = detect_overlaps_from_rects(
            rects, gap=GAP, page_height=page_height, bottom_margin=BOTTOM_MARGIN,
            max_offset=max_offset,
        )

        # Map overlapping block indices back to manifest idx
        block_to_manifest = {v: k for k, v in idx_to_block.items()}
        for block_i, correction in block_corrections.items():
            if block_i in block_to_manifest:
                all_corrections[block_to_manifest[block_i]] = correction

    doc.close()
    return all_corrections


# ---------------------------------------------------------------------------
# Anchor-based detection (accurate for dense/overlapping margins)
#
# The rendered-block detectors above fail on crowded pages: when margin notes
# overlap, PyMuPDF does not segment them into one-block-per-note, so they go
# undetected.  This detector instead uses the *anchor* position of each note
# (where its \marginnote sits in the body text), recorded in the .aux by the
# geneva_bible.tex \@mn@margintest patch as:
#     \newmarginnote{note.P.N}{{page}{Xsp}}   (page + x of the anchor)
#     \mnypos{note.P.N}{Ysp}                   (y of the anchor, \lastypos)
# Y is measured from the page bottom, so top-down position = PAGE_HEIGHT - Y.
# Each note's height is estimated from its annotation text.  Notes that would
# overlap a kept note (or run off the page) are demoted to footnotes.
# ---------------------------------------------------------------------------

PAGE_HEIGHT_PT = 677.5          # geneva paper height in points (239mm)
_SP = 65536.0                   # scaled points per point
_CHARS_PER_LINE = 12.0          # calibrated from a 197-char / 16-line note
_LINE_HEIGHT_PT = 10.5          # \fontsize{9}{10.5}; slight over-estimate is safe


def estimate_note_height(text: str, letter: str,
                         chars_per_line: float = _CHARS_PER_LINE,
                         line_height: float = _LINE_HEIGHT_PT) -> float:
    """Estimate a margin note's rendered height (pt) from its text length.

    The note renders as ``<letter> <text>``.  Over-estimating slightly is the
    safe direction (footnotes a few more notes -> guarantees no overlap)."""
    n = len(text) + len(letter) + 1
    lines = max(1, math.ceil(n / chars_per_line))
    return lines * line_height


def _parse_anchor_aux(aux_path: str):
    """Parse \\newmarginnote (page,x) and \\mnypos (y) keyed by note name.

    Returns (order, page_of, y_of): order = note names in document order,
    page_of[name] = int page, y_of[name] = int y in sp."""
    order: list[str] = []
    page_of: dict[str, int] = {}
    y_of: dict[str, int] = {}
    nm_pat = re.compile(r"\\newmarginnote\{(note\.\d+\.\d+)\}\{\{(\d+)\}\{(-?\d+)sp\}\}")
    y_pat = re.compile(r"\\mnypos\{(note\.\d+\.\d+)\}\{(-?\d+)sp\}")
    with open(aux_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = nm_pat.match(line)
            if m:
                name = m.group(1)
                order.append(name)
                page_of[name] = int(m.group(2))
                continue
            m = y_pat.match(line)
            if m:
                y_of[m.group(1)] = int(m.group(2))
    return order, page_of, y_of


def _annotation_text(annotations: dict, entry: dict) -> str:
    """Full annotation text for a manifest entry (book/ch/verse/letter)."""
    try:
        notes = annotations[entry["book"]][str(entry["ch"])][str(entry["verse"])]
    except (KeyError, TypeError):
        return entry.get("text_prefix", "")
    for n in notes:
        if n.get("letter") == entry["letter"]:
            return n.get("text", "")
    return entry.get("text_prefix", "")


def detect_from_anchors(
    aux_path: str,
    manifest_path: str,
    annotations_path: str,
    already_footnoted: set | None = None,
    gap: float = GAP,
    bottom_margin: float = BOTTOM_MARGIN,
    page_height: float = PAGE_HEIGHT_PT,
) -> dict:
    """Footnote margin notes that would overlap, using anchor positions.

    Robust on dense pages (independent of how the overlapping text renders).
    Per page, notes are sorted top-to-bottom by anchor position; a note is
    demoted to a footnote if its anchor falls within the previous kept note's
    extent (+gap) or it would run past the usable bottom of the page.

    Returns {manifest_idx: "footnote"} for notes to demote (beyond those
    already in ``already_footnoted``).
    """
    with open(manifest_path) as f:
        manifest = json.load(f)
    if not manifest:
        return {}
    with open(annotations_path, encoding="utf-8") as f:
        annotations = json.load(f)

    footnoted = already_footnoted or set()
    margin_manifest = [e for e in manifest if e["idx"] not in footnoted]

    order, page_of, y_of = _parse_anchor_aux(aux_path)

    # aux entries (one \newmarginnote per non-footnoted \marginnote, document
    # order) align entry-for-entry with margin_manifest.
    per_page: dict[int, list] = {}
    for k, entry in enumerate(margin_manifest):
        if k >= len(order):
            break
        name = order[k]
        y_sp = y_of.get(name)
        if y_sp is None:
            continue
        top = page_height - (y_sp / _SP)            # top-down anchor position
        height = estimate_note_height(_annotation_text(annotations, entry), entry["letter"])
        per_page.setdefault(page_of[name], []).append((entry["idx"], top, height))

    usable_bottom = page_height - bottom_margin
    corrections: dict = {}
    for notes in per_page.values():
        notes.sort(key=lambda t: t[1])
        last_bottom = None
        for idx, top, height in notes:
            overlaps_prev = last_bottom is not None and top < last_bottom + gap
            runs_off = (top + height) > usable_bottom
            if overlaps_prev or runs_off:
                corrections[idx] = "footnote"
            else:
                last_bottom = top + height
    return corrections
