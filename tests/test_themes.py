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
            ".bz-wire", ".heat", ".tape-inner", ".bz-strip", ".bz-idxc"]
    for key, css in themes.THEME_CSS.items():
        for cls in core:
            assert cls in css, f"{key} missing {cls}"


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
