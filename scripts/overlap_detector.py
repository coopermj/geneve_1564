"""Detect overlapping margin notes in a compiled PDF using PyMuPDF."""

import json
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
