from overlap_detector import detect_overlaps_from_rects, _identify_margin_notes

PAGE_WIDTH = 507.0
PAGE_HEIGHT = 677.0
MARGIN_X = 435.0


def test_no_overlap():
    rects = [(436, 100, 500, 120), (436, 125, 500, 145)]
    corrections = detect_overlaps_from_rects(rects, gap=2.0, page_height=PAGE_HEIGHT)
    assert corrections == {}


def test_single_overlap():
    # Note 0 ends at y=120, note 1 starts at y=115 — overlap of 5pt
    rects = [(436, 100, 500, 120), (436, 115, 500, 135)]
    corrections = detect_overlaps_from_rects(rects, gap=2.0, page_height=PAGE_HEIGHT)
    # Note 1 should be pushed down by (120 + 2) - 115 = 7pt
    assert 1 in corrections
    assert abs(corrections[1] - 7.0) < 0.1


def test_cascade_overlap():
    # Three notes: 0 and 1 overlap, pushing 1 causes 1 and 2 to overlap
    rects = [(436, 100, 500, 120), (436, 115, 500, 135), (436, 132, 500, 152)]
    corrections = detect_overlaps_from_rects(rects, gap=2.0, page_height=PAGE_HEIGHT)
    assert 1 in corrections
    assert 2 in corrections
    assert corrections[2] > corrections[1]


def test_footnote_fallback_when_off_page():
    rects = [(436, 600, 500, 620), (436, 610, 500, 630)]
    corrections = detect_overlaps_from_rects(
        rects, gap=2.0, page_height=PAGE_HEIGHT, bottom_margin=36.0
    )
    # 620 + 2 = 622, note 1 bottom = 622 + 20 = 642 > 677 - 36 = 641 → footnote
    assert corrections[1] == "footnote"


def test_identify_margin_notes_filters_by_x():
    blocks = [
        {"bbox": (50, 100, 400, 110), "text": "main text"},
        {"bbox": (440, 100, 500, 110), "text": "(a) right margin note"},
        {"bbox": (440, 200, 500, 210), "text": "(b) another right note"},
        # A block whose right edge is in the left margin zone
        {"bbox": (10, 150, 60, 160), "text": "left margin note"},
    ]
    left, right = _identify_margin_notes(blocks, margin_x=435.0)
    # Right: two blocks with x0 > 435
    assert len(right) == 2
    assert right[0]["text"] == "(a) right margin note"
    # Left: one block whose x1 < 435/0.86 * LEFT_MARGIN_FRAC ≈ 89
    assert len(left) == 1
    assert left[0]["text"] == "left margin note"
