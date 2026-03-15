"""Detect overlapping margin notes in a compiled PDF using PyMuPDF."""

import json
import os

import fitz  # PyMuPDF

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

GAP = 2.0
BOTTOM_MARGIN = 36.0

# In twocolumn mode, marginnote places notes in the outer margin of the
# current column: left-column text → left margin, right-column text →
# right margin.  The right-margin threshold is 0.86 * page_width (passed
# in as margin_x).  The left-margin threshold is the symmetric fraction
# on the other side: blocks whose *right edge* (x1) is less than
# LEFT_MARGIN_FRAC * page_width are in the left outer margin.
LEFT_MARGIN_FRAC = 0.17  # right edge of left-margin block < 17% of page width


def _identify_margin_notes(blocks: list, margin_x: float) -> tuple[list, list]:
    """Return (left_blocks, right_blocks) for the two outer margin zones.

    In twocolumn layout, notes for column-1 text appear in the LEFT outer
    margin (right edge < LEFT_MARGIN_FRAC * page_width) and notes for
    column-2 text appear in the RIGHT outer margin (left edge > margin_x).
    Each list is sorted top-to-bottom.  The manifest sequence processes
    left-column notes before right-column notes on each page, matching
    the LaTeX two-column flow: column 1 fills before column 2 begins.
    """
    page_width = margin_x / 0.86
    left_threshold = page_width * LEFT_MARGIN_FRAC

    left = sorted(
        [b for b in blocks if b["bbox"][2] < left_threshold],
        key=lambda b: b["bbox"][1],
    )
    right = sorted(
        [b for b in blocks if b["bbox"][0] > margin_x],
        key=lambda b: b["bbox"][1],
    )
    return left, right


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


def detect(
    pdf_path: str,
    manifest_path: str,
    max_offset: float | None = None,
    already_footnoted: set | None = None,
) -> dict:
    """Detect overlapping margin notes in a compiled PDF.

    Matches margin notes in the PDF (by sequence) to manifest entries,
    returns corrections keyed by manifest idx.

    Args:
        already_footnoted: Set of manifest idx values already demoted to
            footnotes. These are skipped during sequential matching so the
            PDF margin blocks stay aligned with the remaining manifest entries.
    """
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    if not manifest:
        return {}

    footnoted = already_footnoted or set()
    # Build ordered list of manifest entries that are still margin notes
    margin_manifest = [e for e in manifest if e["idx"] not in footnoted]

    doc = fitz.open(pdf_path)
    all_corrections: dict = {}
    global_note_idx = 0

    for page in doc:
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
        left_blocks, right_blocks = _identify_margin_notes(text_blocks, margin_x=margin_x)

        # Detect overlaps in each column independently, then map to manifest
        # in left-first, right-second order (matching the LaTeX sequence).
        col_offset = 0
        page_corrections: dict = {}
        for col_blocks in (left_blocks, right_blocks):
            rects = [b["bbox"] for b in col_blocks]
            col_corr = detect_overlaps_from_rects(
                rects, gap=GAP, page_height=page_height, bottom_margin=BOTTOM_MARGIN,
                max_offset=max_offset,
            )
            for local_i, val in col_corr.items():
                page_corrections[local_i + col_offset] = val
            col_offset += len(rects)

        total_blocks = col_offset
        for local_i in range(total_blocks):
            if global_note_idx >= len(margin_manifest):
                break
            if local_i in page_corrections:
                manifest_idx = margin_manifest[global_note_idx]["idx"]
                all_corrections[manifest_idx] = page_corrections[local_i]
            global_note_idx += 1

    doc.close()
    return all_corrections
