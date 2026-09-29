"""Tests for web.py's paginate() helper.

web.py can't be imported in unit tests (it needs a Streamlit runtime),
so the pure function is extracted via AST and exec'd in isolation.
"""

import ast
from pathlib import Path


def _load_paginate():
    src = (Path(__file__).parent.parent / "web.py").read_text()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "paginate":
            ns = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         "web.py", "exec"), ns)
            return ns["paginate"]
    raise AssertionError("paginate not found in web.py")


paginate = _load_paginate()


def test_first_page():
    vis, rem = paginate(list(range(20)), 1, 8)
    assert vis == list(range(8))
    assert rem == list(range(8, 20))


def test_second_page():
    vis, rem = paginate(list(range(20)), 2, 8)
    assert vis == list(range(16))
    assert rem == list(range(16, 20))


def test_last_page_empty_remaining():
    vis, rem = paginate(list(range(20)), 3, 8)
    assert vis == list(range(20))
    assert rem == []


def test_short_list():
    vis, rem = paginate(["a", "b"], 1, 8)
    assert vis == ["a", "b"]
    assert rem == []


def test_empty():
    assert paginate([], 1, 8) == ([], [])


def test_page_clamped():
    vis, rem = paginate(list(range(10)), 0, 8)
    assert vis == list(range(8))
    assert rem == [8, 9]
