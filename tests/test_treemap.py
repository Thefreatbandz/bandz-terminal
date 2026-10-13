"""Tests for marketpulse.treemap (squarified treemap layout)."""
import math

from marketpulse.treemap import layout


def _items(weights, tag="T"):
    return [{"name": f"{tag}{i}", "weight": w} for i, w in enumerate(weights)]


def _pairwise_disjoint(tiles):
    """Rects must not intersect with positive area (touching edges OK)."""
    for i in range(len(tiles)):
        a = tiles[i]
        ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
        for j in range(i + 1, len(tiles)):
            b = tiles[j]
            bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
            inter_w = min(ax2, bx2) - max(a["x"], b["x"])
            inter_h = min(ay2, by2) - max(a["y"], b["y"])
            assert not (inter_w > 1e-9 and inter_h > 1e-9), \
                f"tiles {i} and {j} overlap with positive area"


def _assert_invariant(tiles, weights, width, height):
    # Proportionality: each tile's area fraction vs weight fraction within 1%.
    total = sum(weights)
    expected = sorted((w / total for w in weights), reverse=True)
    got = sorted((t["w"] * t["h"] / (width * height) for t in tiles), reverse=True)
    assert len(got) == len(expected)
    for g, e in zip(got, expected):
        assert abs(g - e) <= 0.01, f"area fraction {g} vs expected {e}"
    # No overlaps.
    _pairwise_disjoint(tiles)
    # Fills the rect within 0.1% relative.
    area = sum(t["w"] * t["h"] for t in tiles)
    assert math.isclose(area, width * height, rel_tol=0.001), \
        f"total area {area} vs rect {width * height}"
    # Bounds and non-negativity.
    for t in tiles:
        assert 0.0 <= t["x"] <= width
        assert 0.0 <= t["y"] <= height
        assert 0.0 <= t["w"] <= width
        assert 0.0 <= t["h"] <= height
        assert t["x"] + t["w"] <= width + 1e-9
        assert t["y"] + t["h"] <= height + 1e-9


def test_proportionality_no_overlap_and_fill():
    weights = [50, 30, 20]
    tiles = layout(_items(weights), 1000, 1000)
    assert len(tiles) == 3
    _assert_invariant(tiles, weights, 1000, 1000)


def test_non_square_rect():
    weights = [50, 30, 20]
    tiles = layout(_items(weights), 1600, 900)
    _assert_invariant(tiles, weights, 1600, 900)


def test_empty_input():
    assert layout([]) == []


def test_all_weights_filtered():
    assert layout([{"weight": 0}, {"weight": -5}]) == []


def test_zero_negative_missing_and_nonnumeric_filtered():
    items = [
        {"name": "good", "weight": 10},
        {"name": "zero", "weight": 0},
        {"name": "neg", "weight": -3},
        {"name": "missing"},
        {"name": "string", "weight": "10"},
        {"name": "none", "weight": None},
        {"name": "bool", "weight": True},
        {"name": "nan", "weight": float("nan")},
    ]
    tiles = layout(items, 1000, 1000)
    assert len(tiles) == 1
    assert tiles[0]["name"] == "good"
    assert tiles[0]["w"] == 1000.0 and tiles[0]["h"] == 1000.0


def test_input_dicts_not_mutated():
    items = _items([50, 30, 20])
    layout(items, 1000, 1000)
    for d in items:
        assert "x" not in d and "y" not in d and "w" not in d and "h" not in d
    # Returned dicts are copies, not the originals.
    tiles = layout(items, 1000, 1000)
    assert all(t is not d for t, d in zip(tiles, items))


def test_single_item_fills_rect():
    tiles = layout([{"name": "only", "weight": 42}], 800, 600)
    assert len(tiles) == 1
    t = tiles[0]
    assert t["x"] == 0.0 and t["y"] == 0.0
    assert t["w"] == 800.0 and t["h"] == 600.0


def test_bad_dimensions_return_empty():
    items = _items([10, 20])
    assert layout(items, 0, 1000) == []
    assert layout(items, 1000, 0) == []
    assert layout(items, -5, 100) == []
    assert layout(items, 100, -1) == []


def test_larger_case():
    weights = list(range(1, 41))  # 40 items, 1..40
    tiles = layout(_items(weights), 1000, 1000)
    assert len(tiles) == 40
    _assert_invariant(tiles, weights, 1000, 1000)


def test_equal_weights():
    weights = [1] * 16
    tiles = layout(_items(weights), 400, 400)
    assert len(tiles) == 16
    _assert_invariant(tiles, weights, 400, 400)


def test_preserves_extra_keys_and_sorts_descending():
    items = [
        {"symbol": "B", "weight": 20},
        {"symbol": "A", "weight": 70},
        {"symbol": "C", "weight": 10},
    ]
    tiles = layout(items, 1000, 1000)
    symbols = [t["symbol"] for t in tiles]
    assert symbols == ["A", "B", "C"]  # sorted by weight descending
    areas = [t["w"] * t["h"] for t in tiles]
    assert areas[0] > areas[1] > areas[2]
