"""History store tests.

Uses an isolated temp directory via the ``LYNX_DASHBOARD_HISTORY`` env var
override so tests never touch the user's real history file.
"""

from __future__ import annotations

import json

import pytest

from lynx_dashboard.history import HistoryEntry, HistoryStore, default_history_path


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def test_default_history_path_respects_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LYNX_DASHBOARD_HISTORY", str(tmp_path / "custom.json"))
    assert default_history_path() == tmp_path / "custom.json"


def test_default_history_path_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("LYNX_DASHBOARD_HISTORY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert default_history_path() == tmp_path / "xdg" / "lynx-dashboard" / "history.json"


def test_default_history_path_home_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("LYNX_DASHBOARD_HISTORY", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "home")
    assert default_history_path() == tmp_path / "home" / ".config" / "lynx-dashboard" / "history.json"


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------

def test_missing_file_returns_empty(tmp_path):
    store = HistoryStore(path=tmp_path / "nope.json")
    assert store.load() == []
    assert store.recent_queries() == []


def test_corrupted_file_returns_empty(tmp_path):
    path = tmp_path / "hist.json"
    path.write_text("{not-json")
    store = HistoryStore(path=path)
    assert store.load() == []


def test_non_list_file_returns_empty(tmp_path):
    path = tmp_path / "hist.json"
    path.write_text('{"foo": "bar"}')
    assert HistoryStore(path=path).load() == []


def test_record_and_reload(tmp_path):
    path = tmp_path / "hist.json"
    s1 = HistoryStore(path=path)
    s1.record(HistoryEntry(query="AAPL", ticker="AAPL", sector="Technology",
                           primary="lynx-investor-information-technology"))
    s1.record(HistoryEntry(query="XOM", ticker="XOM", sector="Energy",
                           primary="lynx-investor-energy"))

    # Fresh store reads from disk.
    s2 = HistoryStore(path=path)
    loaded = s2.load()
    assert [e.query for e in loaded] == ["XOM", "AAPL"]  # most-recent first


def test_duplicate_queries_deduped_case_insensitive(tmp_path):
    store = HistoryStore(path=tmp_path / "hist.json")
    store.record(HistoryEntry(query="aapl"))
    store.record(HistoryEntry(query="XOM"))
    store.record(HistoryEntry(query="AAPL"))  # re-adds as newest, dedup aapl
    queries = [e.query for e in store.load()]
    assert queries == ["AAPL", "XOM"]


def test_limit_truncates(tmp_path):
    store = HistoryStore(path=tmp_path / "hist.json", limit=3)
    for ticker in ["AAPL", "MSFT", "XOM", "JPM", "BA"]:
        store.record(HistoryEntry(query=ticker))
    assert [e.query for e in store.load()] == ["BA", "JPM", "XOM"]


def test_empty_query_is_ignored(tmp_path):
    store = HistoryStore(path=tmp_path / "hist.json")
    store.record(HistoryEntry(query=""))
    store.record(HistoryEntry(query="   "))
    assert store.load() == []


def test_recent_queries_flat_order_and_dedup(tmp_path):
    store = HistoryStore(path=tmp_path / "hist.json")
    for q in ["AAPL", "xom", "AAPL", "JPM"]:
        store.record(HistoryEntry(query=q))
    # Most recent first, de-duplicated case-insensitively.
    assert store.recent_queries(max_items=3) == ["JPM", "AAPL", "xom"]


def test_clear_removes_file(tmp_path):
    path = tmp_path / "hist.json"
    store = HistoryStore(path=path)
    store.record(HistoryEntry(query="AAPL"))
    assert path.exists()
    store.clear()
    assert not path.exists()
    assert store.load() == []


def test_write_is_json_serializable(tmp_path):
    path = tmp_path / "hist.json"
    store = HistoryStore(path=path)
    store.record(HistoryEntry(query="AAPL", ticker="AAPL", sector="Technology"))
    # File is valid JSON that round-trips cleanly.
    payload = json.loads(path.read_text())
    assert isinstance(payload, list)
    assert payload[0]["query"] == "AAPL"
    assert payload[0]["sector"] == "Technology"


def test_write_is_atomic_via_tmp_file(tmp_path, monkeypatch):
    """Abort mid-write must not corrupt the existing history."""
    path = tmp_path / "hist.json"
    store = HistoryStore(path=path)
    store.record(HistoryEntry(query="AAPL"))
    original = path.read_text()

    # Force replace to fail half-way: patch Path.replace to raise.
    def broken_replace(self, target):
        raise OSError("disk full")
    monkeypatch.setattr("pathlib.Path.replace", broken_replace)

    # Store is non-fatal on OSError — record swallows it.
    store.record(HistoryEntry(query="XOM"))
    # Original file untouched.
    assert path.read_text() == original
