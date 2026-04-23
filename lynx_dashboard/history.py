"""Persistent recent-queries store.

Keeps the last *N* recommender queries in a JSON file under the user's
standard config directory. Used by the GUI / TUI Recommend dialogs to
show clickable "recently searched" pills.

Storage is deliberately minimal: a list of ``{ "query": ..., "ticker":
..., "sector": ..., "primary": ..., "ts": ... }`` dicts in a single file.
No SQLite, no locks — if two dashboard processes run concurrently the
latter wins, which is fine for a personal tool.

Location priority:
  1. ``$LYNX_DASHBOARD_HISTORY`` (explicit override for tests + power users)
  2. ``$XDG_CONFIG_HOME/lynx-dashboard/history.json``
  3. ``~/.config/lynx-dashboard/history.json``
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


__all__ = [
    "HistoryEntry",
    "HistoryStore",
    "default_history_path",
]


DEFAULT_LIMIT = 12


@dataclass(frozen=True)
class HistoryEntry:
    """A single recorded recommendation."""
    query: str                            # what the user typed
    ticker: str = ""                      # resolved Yahoo symbol (may be empty)
    sector: str = ""                      # classified sector (may be empty)
    primary: str = ""                     # suggested agent's registry_name
    ts: float = field(default_factory=time.time)

    def as_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "HistoryEntry":
        return cls(
            query=str(data.get("query", "")),
            ticker=str(data.get("ticker", "")),
            sector=str(data.get("sector", "")),
            primary=str(data.get("primary", "")),
            ts=float(data.get("ts", 0.0) or 0.0),
        )


def default_history_path() -> Path:
    """Compute the history file path from env / XDG / ~/.config."""
    explicit = os.environ.get("LYNX_DASHBOARD_HISTORY")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "lynx-dashboard" / "history.json"


class HistoryStore:
    """Simple file-backed history store with an in-memory cache."""

    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.path = Path(path) if path is not None else default_history_path()
        self.limit = max(1, int(limit))
        self._cache: Optional[List[HistoryEntry]] = None

    # -- read ----------------------------------------------------------

    def load(self) -> List[HistoryEntry]:
        """Return the stored history (most-recent first). Cached in memory."""
        if self._cache is not None:
            return list(self._cache)
        entries: List[HistoryEntry] = []
        try:
            raw = self.path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError, PermissionError):
            self._cache = []
            return []
        try:
            payload = json.loads(raw) if raw.strip() else []
        except (ValueError, json.JSONDecodeError):
            # Corrupted history file — don't crash the dashboard. Reset.
            self._cache = []
            return []
        if not isinstance(payload, list):
            self._cache = []
            return []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                entries.append(HistoryEntry.from_json(item))
            except (TypeError, ValueError):
                continue
        self._cache = entries[: self.limit]
        return list(self._cache)

    def recent_queries(self, max_items: Optional[int] = None) -> List[str]:
        """Flat list of the most-recent queries, deduped preserving order."""
        n = max_items if max_items is not None else self.limit
        seen: set = set()
        out: List[str] = []
        for entry in self.load():
            q = entry.query.strip()
            if not q or q.lower() in seen:
                continue
            seen.add(q.lower())
            out.append(q)
            if len(out) >= n:
                break
        return out

    # -- write ---------------------------------------------------------

    def record(self, entry: HistoryEntry) -> None:
        """Prepend *entry*, de-dup by query (case-insensitive), truncate."""
        if not entry.query.strip():
            return
        entries = self.load()
        query_lower = entry.query.strip().lower()
        deduped = [
            existing for existing in entries
            if existing.query.strip().lower() != query_lower
        ]
        deduped.insert(0, entry)
        self._cache = deduped[: self.limit]
        self._flush()

    def clear(self) -> None:
        self._cache = []
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass

    def _flush(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = [entry.as_json() for entry in (self._cache or [])]
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            # Non-fatal: history is a convenience, not a correctness feature.
            pass
