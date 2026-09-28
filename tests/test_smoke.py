"""Full render smoke test: runs web.py top-to-bottom in a real Streamlit
script context (AppTest). Catches runtime TypeErrors etc. that
py_compile and unit tests cannot see -- e.g. the 2026-09-28 outage where
a bad smd() call crashed the app on every page load on Streamlit Cloud.
Takes ~60s (live network fallbacks); run before every push.
"""
import pytest
from pathlib import Path

pytestmark = pytest.mark.slow


def test_web_renders_without_exception():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "web.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"web.py raised: {at.exception[0] if at.exception else ''}"
    # Header strip rendered
    assert any("BANDZ TERMINAL" in str(m.value) for m in at.markdown)
