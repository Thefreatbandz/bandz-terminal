"""Tests for the theme switcher (marketpulse/themes.py)."""

import json

from marketpulse import themes


def test_all_four_themes_present():
    assert set(themes.THEME_CSS) == {"cyber", "gold", "retro", "space"}
    assert set(themes.THEMES) == {"cyber", "gold", "retro", "space"}


def test_css_blocks_well_formed():
    for key, css in themes.THEME_CSS.items():
        css = css.strip()
        assert css.startswith("<style>"), key
        assert css.endswith("</style>"), key
        assert len(css) > 1000, key


def test_all_themes_share_class_set():
    # The HTML in web.py doesn't change, so every theme must define the
    # same core classes.
    core = [".bz-card", ".bz-sym", ".bz-price", ".bz-chg", ".bz-sec",
            ".bz-wire", ".heat", ".bz-strip", ".bz-idxc"]
    for key, css in themes.THEME_CSS.items():
        for cls in core:
            assert cls in css, f"{key} missing {cls}"


def test_shared_css_well_formed():
    css = themes.SHARED_CSS.strip()
    assert css.startswith("<style>")
    assert css.endswith("</style>")
    assert len(css) > 500


def test_shared_css_ticker_strip():
    # Snap-scroll strip replaces the infinite marquee (perf).
    assert ".tape-strip" in themes.SHARED_CSS
    assert ".tape-chip" in themes.SHARED_CSS
    assert "scroll-snap-type" in themes.SHARED_CSS
    assert "tape-scroll" not in themes.SHARED_CSS
    for key, css in themes.THEME_CSS.items():
        assert "tape-scroll" not in css, f"{key} still has marquee"


def test_shared_css_motion_and_mobile():
    assert "prefers-reduced-motion" in themes.SHARED_CSS
    assert "max-width: 640px" in themes.SHARED_CSS


def test_theme_accent_vars():
    expected = {"cyber": "#22d3ee", "gold": "#d4af37",
                "retro": "#ffb000", "space": "#22d3ee"}
    for key, accent in expected.items():
        css = themes.THEME_CSS[key]
        assert f"--accent: {accent}" in css, key
        assert "--up:" in css and "--down:" in css, key


def test_shared_css_richness_layer():
    css = themes.SHARED_CSS
    for sel in (".bz-card::before", ".bz-card.up::before",
                ".bz-card.down::before", ".bz-strip::before",
                ".bz-sec::after", ".tape-chip", ".bz-spark",
                '[data-testid="stBaseButton-primary"]'):
        assert sel in css, sel
    assert "var(--accent)" in css
    assert ".bz-num" in css
    assert "overflow: visible" in css
    # No glow, no animation in the richness layer
    assert "box-shadow: 0 0" not in css
    assert "@keyframes" not in css


def test_load_theme_defaults_to_cyber(tmp_path, monkeypatch):
    monkeypatch.setattr(themes, "THEME_FILE", str(tmp_path / "theme.json"))
    assert themes.load_theme() == "cyber"


def test_save_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(themes, "THEME_FILE", str(tmp_path / "theme.json"))
    themes.save_theme("retro")
    assert themes.load_theme() == "retro"
    data = json.loads((tmp_path / "theme.json").read_text())
    assert data == {"theme": "retro"}


def test_load_theme_rejects_unknown_key(tmp_path, monkeypatch):
    p = tmp_path / "theme.json"
    p.write_text(json.dumps({"theme": "neon-banana"}))
    monkeypatch.setattr(themes, "THEME_FILE", str(p))
    assert themes.load_theme() == "cyber"


def test_load_theme_handles_corrupt_file(tmp_path, monkeypatch):
    p = tmp_path / "theme.json"
    p.write_text("not json {{{")
    monkeypatch.setattr(themes, "THEME_FILE", str(p))
    assert themes.load_theme() == "cyber"


def test_save_theme_rejects_unknown_key(tmp_path, monkeypatch):
    p = tmp_path / "theme.json"
    monkeypatch.setattr(themes, "THEME_FILE", str(p))
    themes.save_theme("neon-banana")
    assert not p.exists()
