"""Detect overlapping margin notes in a compiled PDF using PyMuPDF."""

import json
import os

import fitz  # PyMuPDF

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

GAP = 2.0
BOTTOM_MARGIN = 36.0


def _identify_margin_notes(blocks: list, margin_x: float) -> list:
    """Filter text blocks to those in the outer margin zone."""
    return [b for b in blocks if b["bbox"][0] > margin_x]


def detect_overlaps_from_rects(
    rects: list[tuple],
    gap: float = GAP,
    page_height: float = 677.0,
    bottom_margin: float = BOTTOM_MARGIN,
) -> dict:
    """Detect overlapping bounding boxes and compute push-down corrections.

    Args:
        rects: List of (x0, y0, x1, y1) tuples, sorted by y0.
        gap: Minimum gap in points between notes.
        page_height: Page height in points.
        bottom_margin: Notes pushed past (page_height - bottom_margin) → footnote.

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
            else:
                corrections[i + 1] = total

    return corrections


def detect(pdf_path: str, manifest_path: str) -> dict:
    """Detect overlapping margin notes in a compiled PDF.

    Matches margin notes in the PDF (by sequence) to manifest entries,
    returns corrections keyed by manifest idx.
    """
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    if not manifest:
        return {}

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
        margin_blocks = _identify_margin_notes(text_blocks, margin_x=margin_x)
        margin_blocks.sort(key=lambda b: b["bbox"][1])

        rects = [b["bbox"] for b in margin_blocks]
        page_corrections = detect_overlaps_from_rects(
            rects, gap=GAP, page_height=page_height, bottom_margin=BOTTOM_MARGIN
        )

        for local_i in range(len(rects)):
            if global_note_idx >= len(manifest):
                break
            if local_i in page_corrections:
                manifest_idx = manifest[global_note_idx]["idx"]
                all_corrections[manifest_idx] = page_corrections[local_i]
            global_note_idx += 1

    doc.close()
    return all_corrections
