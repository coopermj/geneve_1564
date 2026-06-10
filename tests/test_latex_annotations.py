import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from latex_generator import _build_annotation_suffix

ANNOTATIONS_V1 = [{"letter": "a", "text": "First of all, and before any creature was."}]
ANNOTATIONS_V2 = [
    {"letter": "b", "text": "An unformed lump."},
    {"letter": "c", "text": "That is, the waters."},
]


def test_no_annotations_returns_empty():
    counter = [0]
    manifest = []
    result = _build_annotation_suffix("genesis", 1, 1, [], counter, manifest)
    assert result == ""
    assert counter[0] == 0
    assert manifest == []


def test_single_annotation():
    counter = [0]
    manifest = []
    result = _build_annotation_suffix("genesis", 1, 1, ANNOTATIONS_V1, counter, manifest)
    assert r"\gva{a}" in result
    assert r"\marginnote" in result
    assert "First of all" in result
    assert counter[0] == 1
    assert manifest == [{"idx": 0, "book": "genesis", "ch": 1, "verse": 1, "letter": "a", "text_prefix": "First of all, and be"}]


def test_two_annotations():
    counter = [0]
    manifest = []
    result = _build_annotation_suffix("genesis", 1, 2, ANNOTATIONS_V2, counter, manifest)
    assert result.count(r"\gva{") == 4  # 2 inline + 2 in marginnote
    assert result.count(r"\marginnote") == 2
    assert counter[0] == 2


def test_counter_increments_across_calls():
    counter = [5]
    manifest = []
    _build_annotation_suffix("genesis", 1, 1, ANNOTATIONS_V1, counter, manifest)
    assert counter[0] == 6
    assert manifest[0]["idx"] == 5


def test_footnote_fallback():
    counter = [0]
    manifest = []
    corrections = {0: "footnote"}
    result = _build_annotation_suffix(
        "genesis", 1, 1, ANNOTATIONS_V1, counter, manifest, corrections
    )
    assert r"\footnote" in result
    assert r"\marginnote" not in result
    # The annotation letter IS the footnote mark (group-local \thefootnote),
    # replacing both the inline \gva marker and the default numeric mark.
    assert r"\renewcommand{\thefootnote}{\textit{a}}" in result
    assert r"\gva" not in result


def test_offset_correction():
    # Numeric corrections are ignored (only "footnote" corrections are acted on).
    # Any overlapping note that isn't explicitly demoted stays as a marginnote.
    counter = [0]
    manifest = []
    corrections = {0: 24.5}
    result = _build_annotation_suffix(
        "genesis", 1, 1, ANNOTATIONS_V1, counter, manifest, corrections
    )
    assert r"\marginnote{" in result
    assert r"\footnotemain{" not in result


def test_annotation_text_latex_escaped():
    counter = [0]
    manifest = []
    anns = [{"letter": "a", "text": "Text with & ampersand and % percent."}]
    result = _build_annotation_suffix("genesis", 1, 1, anns, counter, manifest)
    assert r"\&" in result
    assert r"\%" in result
