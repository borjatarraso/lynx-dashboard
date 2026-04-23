"""Tests for the splash module (display-free parts only)."""

from __future__ import annotations

import pytest

from lynx_dashboard.splash import (
    _STATUS_STEPS,
    _ease_out_cubic,
    _status_at,
    splash_disabled,
)


def test_ease_out_cubic_bounds():
    """Easing must hold [0,1] even for out-of-range input."""
    assert _ease_out_cubic(0.0) == 0.0
    assert _ease_out_cubic(1.0) == 1.0
    assert _ease_out_cubic(-5.0) == 0.0
    assert _ease_out_cubic(42.0) == 1.0


def test_ease_out_cubic_monotonic():
    """Eased progress must never go backwards — otherwise the bar would rubber-band."""
    prev = -1.0
    for i in range(21):
        v = _ease_out_cubic(i / 20)
        assert v >= prev, f"non-monotonic at {i}: {v} < {prev}"
        prev = v


def test_status_at_walks_through_all_steps():
    """Early t picks the first message, late t picks the last — users should
    read every line during a normal splash."""
    assert _status_at(0.0) == _STATUS_STEPS[0]
    assert _status_at(1.0) == _STATUS_STEPS[-1]
    # And the transitions between steps are ordered.
    seen = []
    for i in range(len(_STATUS_STEPS) + 2):
        seen.append(_status_at(i / (len(_STATUS_STEPS) + 1)))
    # No gaps in the order of unique messages we saw.
    unique = list(dict.fromkeys(seen))
    for i, msg in enumerate(unique):
        assert msg == _STATUS_STEPS[i]


def test_splash_disabled_respects_cli_flag():
    assert splash_disabled(cli_flag=True) is True


def test_splash_disabled_respects_env(monkeypatch):
    monkeypatch.setenv("LYNX_NO_SPLASH", "1")
    assert splash_disabled() is True
    monkeypatch.setenv("LYNX_NO_SPLASH", "true")
    assert splash_disabled() is True


def test_splash_disabled_respects_ci_env(monkeypatch):
    monkeypatch.delenv("LYNX_NO_SPLASH", raising=False)
    monkeypatch.setenv("CI", "true")
    assert splash_disabled() is True


def test_splash_enabled_when_no_signals(monkeypatch):
    monkeypatch.delenv("LYNX_NO_SPLASH", raising=False)
    monkeypatch.delenv("CI", raising=False)
    assert splash_disabled() is False


import math
from lynx_dashboard.splash import _clamp_fraction


def test_easing_handles_nan():
    """NaN must collapse to 0.0 — crashing the splash is a worse UX than a
    stuttering progress bar."""
    assert _ease_out_cubic(float("nan")) == 0.0
    assert _status_at(float("nan")) == _STATUS_STEPS[0]


def test_easing_handles_infinities():
    assert _ease_out_cubic(float("inf")) == 1.0
    assert _ease_out_cubic(float("-inf")) == 0.0
    assert _status_at(float("inf")) == _STATUS_STEPS[-1]
    assert _status_at(float("-inf")) == _STATUS_STEPS[0]


def test_clamp_fraction_direct():
    assert _clamp_fraction(0.5) == 0.5
    assert _clamp_fraction(-5.0) == 0.0
    assert _clamp_fraction(100.0) == 1.0
    assert _clamp_fraction(float("nan")) == 0.0
    assert math.isclose(_clamp_fraction(1.0), 1.0)
