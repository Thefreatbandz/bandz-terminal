"""Tests for web.py's spark_svg().

web.py can't be imported in unit tests (it needs a Streamlit runtime),
so the function plus its id counter are extracted via AST and exec'd
in isolation.
"""

import ast
import itertools
from pathlib import Path


def _load_spark():
    src = (Path(__file__).parent.parent / "web.py").read_text()
    tree = ast.parse(src)
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "spark_svg":
            nodes.append(node)
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "_spark_ids"
                        for t in node.targets)):
            nodes.append(node)
    assert nodes, "spark_svg not found in web.py"
    ns = {"itertools": itertools}
    exec(compile(ast.Module(body=nodes, type_ignores=[]),
                 "web.py", "exec"), ns)
    return ns["spark_svg"]


spark_svg = _load_spark()


def test_up_series_green_with_gradient_fill():
    svg = spark_svg([100, 102, 101, 105])
    assert "<linearGradient" in svg
    assert "<polygon" in svg  # area fill
    assert "<circle" in svg  # end dot
    assert "#34d399" in svg
    assert "#f87171" not in svg


def test_down_series_red():
    svg = spark_svg([105, 102, 101, 100])
    assert "#f87171" in svg
    assert "#34d399" not in svg


def test_gradient_ids_unique_per_call():
    a = spark_svg([1, 2, 3])
    b = spark_svg([1, 2, 3])
    assert 'id="sg' in a and 'id="sg' in b
    assert a.split('id="')[1].split('"')[0] != b.split('id="')[1].split('"')[0]


def test_too_few_points_empty():
    assert spark_svg([100]) == ""
    assert spark_svg([]) == ""


def test_line_joins_round():
    svg = spark_svg([1, 2, 3, 4])
    assert 'stroke-linejoin="round"' in svg
    assert 'stroke-linecap="round"' in svg
