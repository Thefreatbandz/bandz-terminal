"""Cleanup regression tests: no emoji, no neon bars, no NEWS label.

web.py can't be imported in unit tests (it needs a Streamlit runtime),
so markup rules are checked against its source and pure helpers are
extracted via AST and exec'd in isolation.
"""

import ast
from pathlib import Path

import pytest

from marketpulse import themes


def _web_source():
    return (Path(__file__).parent.parent / "web.py").read_text()


def _extract_func(name):
    tree = ast.parse(_web_source())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            ns = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         "web.py", "exec"), ns)
            return ns[name]
    raise AssertionError(f"{name} not found in web.py")


def _func_source(name):
    tree = ast.parse(_web_source())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(_web_source(), node)
    raise AssertionError(f"{name} not found in web.py")


def test_no_neon_cyan_in_markup():
    assert "#00e5ff" not in _web_source()


def test_no_emoji_in_watch_card():
    src = _func_source("watch_card")
    assert "move_emoji" not in src


def test_no_news_label_in_card():
    src = _func_source("watch_card")
    assert ">NEWS</span>" not in src


def test_no_score_bar_in_card():
    src = _func_source("watch_card")
    # the score keeps its quiet label, but the loud bar is gone
    assert "SCORE" in src
    assert src.count("bz-bar") == 1  # only the 52W range bar remains


def test_range_bar_has_no_inline_color():
    src = _func_source("watch_card")
    assert "background:" not in src


def test_dir_glyph():
    g = _extract_func("dir_glyph")
    assert g(1.5) == "▲"
    assert g(-0.2) == "▼"
    assert g(0.0) == "•"
    assert g(None) == "•"
    assert g("x") == "•"


def test_range_bar_uses_theme_accent():
    css = themes.SHARED_CSS
    assert ".bz-bar > div" in css
    assert "var(--accent)" in css


@pytest.mark.parametrize("theme", ["cyber", "gold", "retro", "space"])
def test_shared_bar_beats_theme_height(theme):
    # shared CSS loads after the theme CSS, so its slimmer bar wins
    css = themes.THEME_CSS[theme] + themes.SHARED_CSS
    assert css.rindex(".bz-bar { height: 4px; }") > css.index(".bz-bar")
