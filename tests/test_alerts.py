"""Alert storage tests -- file-backed, uses a temp path."""

import os

from marketpulse import alerts


def test_add_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "alerts.json")
    made = alerts.add_alert("nvda", 3.0, path=path)
    assert made and made["symbol"] == "NVDA" and made["pct"] == 3.0
    assert made["baseline"] is None
    loaded = alerts.load_alerts(path=path)
    assert len(loaded) == 1 and loaded[0]["id"] == made["id"]


def test_add_rejects_bad_input(tmp_path):
    path = str(tmp_path / "alerts.json")
    assert alerts.add_alert("", 3.0, path=path) is None
    assert alerts.add_alert("NVDA", 0, path=path) is None
    assert alerts.add_alert("NVDA", -2, path=path) is None
    assert alerts.load_alerts(path=path) == []


def test_add_rejects_duplicates(tmp_path):
    path = str(tmp_path / "alerts.json")
    assert alerts.add_alert("NVDA", 3.0, path=path)
    assert alerts.add_alert("nvda", 3.0, path=path) is None
    assert len(alerts.load_alerts(path=path)) == 1


def test_remove_alert(tmp_path):
    path = str(tmp_path / "alerts.json")
    made = alerts.add_alert("TSLA", 5.0, path=path)
    assert alerts.remove_alert(made["id"], path=path) is True
    assert alerts.load_alerts(path=path) == []
    assert alerts.remove_alert("nope", path=path) is False


def test_load_missing_file_returns_empty(tmp_path):
    assert alerts.load_alerts(path=str(tmp_path / "missing.json")) == []
    assert os.path.exists(str(tmp_path / "missing.json")) is False


def test_add_pct_alert_roundtrip(tmp_path):
    path = str(tmp_path / "alerts.json")
    made = alerts.add_pct_alert("nvda", 3.0, path=path)
    assert made and made["type"] == "pct"
    assert made["symbol"] == "NVDA" and made["threshold"] == 3.0
    assert made["last_fired"] is None
    loaded = alerts.load_alerts(path=path)
    assert len(loaded) == 1 and loaded[0]["id"] == made["id"]


def test_add_pct_alert_rejects_bad_input(tmp_path):
    path = str(tmp_path / "alerts.json")
    assert alerts.add_pct_alert("", 3.0, path=path) is None
    assert alerts.add_pct_alert("NVDA", 0, path=path) is None
    assert alerts.add_pct_alert("NVDA", 3.0, path=path)
    assert alerts.add_pct_alert("nvda", 3.0, path=path) is None  # dup
    assert len(alerts.load_alerts(path=path)) == 1


def test_add_keyword_alert_roundtrip(tmp_path):
    path = str(tmp_path / "alerts.json")
    made = alerts.add_keyword_alert("  FDA approval ", path=path)
    assert made and made["type"] == "keyword"
    assert made["keyword"] == "FDA approval" and made["seen"] == []
    loaded = alerts.load_alerts(path=path)
    assert len(loaded) == 1 and loaded[0]["id"] == made["id"]


def test_add_keyword_alert_rejects_bad_input(tmp_path):
    path = str(tmp_path / "alerts.json")
    assert alerts.add_keyword_alert("", path=path) is None
    assert alerts.add_keyword_alert("x", path=path) is None
    assert alerts.add_keyword_alert("FDA", path=path)
    assert alerts.add_keyword_alert("fda", path=path) is None  # dup
    assert len(alerts.load_alerts(path=path)) == 1


def test_mixed_types_coexist(tmp_path):
    path = str(tmp_path / "alerts.json")
    alerts.add_alert("NVDA", 3.0, path=path)
    alerts.add_pct_alert("TSLA", 5.0, path=path)
    alerts.add_keyword_alert("merger", path=path)
    loaded = alerts.load_alerts(path=path)
    assert len(loaded) == 3
    types = {a.get("type", "price") for a in loaded}
    assert types == {"price", "pct", "keyword"}
