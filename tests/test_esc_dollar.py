"""Tests for web.py's esc_dollar().

web.py can't be imported in unit tests (it needs a Streamlit runtime),
so the pure function is extracted via AST and exec'd in isolation.
"""

import ast
from pathlib import Path


def _load_esc_dollar():
    src = (Path(__file__).parent.parent / "web.py").read_text()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "esc_dollar":
            ns = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         "web.py", "exec"), ns)
            return ns["esc_dollar"]
    raise AssertionError("esc_dollar not found in web.py")


esc_dollar = _load_esc_dollar()


def test_dollar_becomes_entity():
    assert esc_dollar("a $5 b") == "a &#36;5 b"


def test_no_backslash_no_raw_dollar():
    out = esc_dollar("Price $352.84, range $300-$400")
    assert "\\" not in out
    assert "$" not in out
    assert out.count("&#36;") == 3


def test_non_string_passthrough():
    assert esc_dollar(None) is None
    assert esc_dollar(42) == 42


def test_empty_string():
    assert esc_dollar("") == ""
