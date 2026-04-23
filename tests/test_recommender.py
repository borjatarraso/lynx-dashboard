"""Recommender offline path tests."""

from __future__ import annotations

from lynx_dashboard.recommender import CompanyProfile, recommend_for_profile, recommend_for_query


def test_empty_query_returns_no_match():
    rec = recommend_for_query("", use_network=False)
    assert not rec.has_match
    assert rec.reason != ""


def test_known_energy_ticker_offline():
    rec = recommend_for_query("XOM", use_network=False)
    assert rec.has_match
    assert rec.primary is not None
    assert rec.primary.registry_name == "lynx-investor-energy"


def test_known_tech_ticker_offline():
    rec = recommend_for_query("AAPL", use_network=False)
    assert rec.has_match
    assert rec.primary is not None
    assert rec.primary.registry_name == "lynx-investor-information-technology"


def test_known_finance_ticker_offline():
    rec = recommend_for_query("JPM", use_network=False)
    assert rec.has_match
    assert rec.primary is not None
    assert rec.primary.registry_name == "lynx-investor-financials"


def test_real_estate_ticker_offline():
    rec = recommend_for_query("PLD", use_network=False)
    assert rec.has_match
    assert rec.primary is not None
    assert rec.primary.registry_name == "lynx-investor-real-estate"


def test_profile_driven_match():
    """The recommender accepts a profile directly (for TUI/test harnesses)."""
    profile = CompanyProfile(ticker="ACME", name="Acme Oil", sector="Energy")
    rec = recommend_for_profile(profile)
    assert rec.has_match
    assert rec.primary is not None
    assert rec.primary.registry_name == "lynx-investor-energy"


def test_mystery_query_returns_graceful_no_match():
    rec = recommend_for_query("totally-unknown-xyz-123", use_network=False)
    assert not rec.has_match
    assert rec.reason, "reason must be non-empty so the user sees *why* it didn't match"
    # Explanation must actually say something; the previous version of this
    # test was satisfied by any non-empty reason, which hid regressions.
    assert "no sector match" in rec.reason.lower() or "tip" in rec.reason.lower()


def test_ticker_field_omitted_for_non_ticker_free_text():
    """Ticker slot stays empty for free-text queries so downstream code
    doesn't pass garbage to yfinance on a retry."""
    rec = recommend_for_query("Exxon Mobil Corporation", use_network=False)
    # Multi-word input — sector still matches via description pattern but
    # the ticker slot must be empty.
    assert rec.profile.ticker == "", f"got {rec.profile.ticker!r}"


def test_ticker_field_preserves_dash_and_dot_symbols():
    """Real symbols like BRK-B and OCO.V must round-trip unchanged."""
    rec = recommend_for_query("BRK-B", use_network=False)
    assert rec.profile.ticker == "BRK-B"
    rec = recommend_for_query("OCO.V", use_network=False)
    assert rec.profile.ticker == "OCO.V"


def test_sector_beats_description_in_ranking():
    """The old pipeline walked AGENT_REGISTRY in order and took the first
    hit — so a description pattern on consumer-discretionary ('e-commerce')
    could beat a sector match on consumer-staples ('consumer defensive').
    The fix is to score sector higher than description.

    Reproduces the real-world Procter & Gamble case: sector=Consumer
    Defensive + industry=Household & Personal Products + description
    containing the phrase 'e-commerce channels'."""
    from lynx_dashboard.recommender import CompanyProfile, recommend_for_profile

    profile = CompanyProfile(
        ticker="PG",
        name="The Procter & Gamble Company",
        sector="Consumer Defensive",
        industry="Household & Personal Products",
        description=(
            "It sells its products through mass merchandisers, social and "
            "e-commerce channels, grocery and specialty beauty stores…"
        ),
    )
    rec = recommend_for_profile(profile)
    assert rec.has_match
    assert rec.primary is not None
    assert rec.primary.registry_name == "lynx-investor-consumer-staples", (
        f"got {rec.primary.registry_name} — sector match should outrank "
        f"description pattern match"
    )


def test_looks_like_symbol_heuristic():
    """The fast-path ticker detector must accept real symbols and reject
    free text. Tests the regex edges so real-world inputs stay predictable."""
    from lynx_dashboard.recommender import _looks_like_symbol

    for good in ("AAPL", "BRK-B", "OCO.V", "005930.KS", "XOM", "T"):
        assert _looks_like_symbol(good), f"rejected good symbol {good!r}"
    for bad in (
        "Apple", "Procter & Gamble", "F3 Uranium", "",
        "toolongbutwithnospaceabc", "an obviously long phrase here",
    ):
        assert not _looks_like_symbol(bad), f"accepted bad symbol {bad!r}"


def test_silence_stdio_context_manager(monkeypatch):
    """Nested prints are swallowed and the context cleanly restores stdio."""
    # Force LYNX_DEBUG off — otherwise _silence_stdio becomes a no-op and
    # this test cross-contaminates with test_cli::test_debug_flag_sets_env.
    monkeypatch.delenv("LYNX_DEBUG", raising=False)

    import io
    import sys
    from lynx_dashboard.recommender import _silence_stdio

    saved_out, saved_err = sys.stdout, sys.stderr
    buf = io.StringIO()
    sys.stdout = buf
    sys.stderr = buf
    try:
        with _silence_stdio():
            print("should vanish")
            print("and this too", file=sys.stderr)
        # Context restored → new prints reach the buffer again.
        print("visible")
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    assert "should vanish" not in buf.getvalue()
    assert "and this too" not in buf.getvalue()
    assert "visible" in buf.getvalue()


def test_silence_stdio_respects_lynx_debug(monkeypatch):
    """When LYNX_DEBUG=1 the silencer is a no-op — diagnostic passthrough."""
    monkeypatch.setenv("LYNX_DEBUG", "1")
    import io
    import sys
    from lynx_dashboard.recommender import _silence_stdio

    saved_out = sys.stdout
    buf = io.StringIO()
    sys.stdout = buf
    try:
        with _silence_stdio():
            print("should appear")
    finally:
        sys.stdout = saved_out
    assert "should appear" in buf.getvalue()


def test_all_eleven_sectors_reachable_offline():
    """Every sector must be reachable via at least one known large-cap ticker."""
    hits = {
        "lynx-investor-energy": "XOM",
        "lynx-investor-financials": "JPM",
        "lynx-investor-information-technology": "AAPL",
        "lynx-investor-healthcare": "JNJ",
        "lynx-investor-basic-materials": "NEM",
        "lynx-investor-consumer-discretionary": "AMZN",
        "lynx-investor-consumer-staples": "PG",
        "lynx-investor-industrials": "BA",
        "lynx-investor-utilities": "NEE",
        "lynx-investor-communication-services": "GOOGL",
        "lynx-investor-real-estate": "PLD",
    }
    for registry_name, ticker in hits.items():
        rec = recommend_for_query(ticker, use_network=False)
        assert rec.has_match, f"{ticker} did not match any agent"
        assert rec.primary is not None
        assert rec.primary.registry_name == registry_name, (
            f"{ticker} expected {registry_name}, got {rec.primary.registry_name}"
        )
