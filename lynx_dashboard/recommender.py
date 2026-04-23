"""Recommend which agent(s) to use for a given company.

Resolution strategy (runs in order; first hit wins):

1. **Ticker fast path** — if the query looks like a plain symbol (``XOM``,
   ``BRK-B``, ``OCO.V``), try ``yfinance.Ticker(query)`` directly. This is
   the quickest path and covers the vast majority of queries.

2. **Core resolver** — hand the raw query to
   ``lynx_investor_core.ticker.resolve_identifier``, which knows how to:
     - treat ISINs (e.g. ``US0378331005``) as ISINs,
     - run a Yahoo search for company names (``Oroco``, ``F3 Uranium``),
     - try 30+ exchange suffixes (``.V``, ``.TO``, ``.DE``, ``.L``, ``.PA``,
       ``.AS``, …) against a bare ticker.

3. **Yahoo search** as a last-chance for short or abbreviated queries like
   ``F3`` that neither a direct ticker nor the resolver matches.

4. **Offline hint table** (hand-curated big-cap list + description-pattern
   scan) when yfinance isn't available or the network is down.

All the sector logic stays in ``lynx_investor_core.sector_registry`` —
we don't duplicate GICS mappings here.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional, Tuple

from lynx_investor_core.sector_registry import AGENT_REGISTRY, AgentEntry

from lynx_dashboard.registry import AGENTS, Launchable, by_registry_name

__all__ = [
    "CompanyProfile",
    "Recommendation",
    "recommend_for_query",
    "recommend_for_profile",
]


@dataclass
class CompanyProfile:
    """Minimal profile shape compatible with ``sector_registry._ProfileLike``."""
    ticker: str = ""
    name: str = ""
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    source: str = "offline"     # "yfinance" or "offline"

    @property
    def has_data(self) -> bool:
        return bool(self.sector or self.industry or self.description)


@dataclass
class Recommendation:
    query: str
    profile: CompanyProfile
    primary: Optional[Launchable] = None
    alternates: List[Launchable] = field(default_factory=list)
    reason: str = ""

    @property
    def has_match(self) -> bool:
        return self.primary is not None

    @property
    def all_agents(self) -> List[Launchable]:
        out = []
        if self.primary is not None:
            out.append(self.primary)
        out.extend(self.alternates)
        return out


# ---------------------------------------------------------------------------
# yfinance integration (optional)
# ---------------------------------------------------------------------------

# Cache resolved (query → profile) pairs so repeat queries in the same session
# don't re-hit the network. maxsize=256 is plenty for an interactive dashboard
# and bounds memory if someone scripts a pathological workload.
@lru_cache(maxsize=256)
def _cached_yf_profile(query: str) -> Optional[CompanyProfile]:
    return _fetch_yf_profile_uncached(query)


def _fetch_yf_profile(query: str) -> Optional[CompanyProfile]:
    """Fetch a Yahoo Finance profile for *query*, resolving names & ISINs."""
    return _cached_yf_profile(query.strip())


def _fetch_yf_profile_uncached(query: str) -> Optional[CompanyProfile]:
    """Resolution pipeline. Each step yields zero or more candidate symbols;
    we return the first candidate whose profile has usable sector data.

    A single step succeeding at the "valid Ticker" level isn't enough: some
    exchange-suffixed symbols (``STM.MI``) resolve to a Yahoo entry that
    carries a name but no sector/industry. In that case we keep trying
    more candidates — including name-based search derived from the Ticker
    whose name we *did* see — so the user gets a real classification
    whenever the underlying company is known to Yahoo at all.
    """
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return None

    query = query.strip()
    if not query:
        return None

    tried: set = set()

    def _try_symbol(symbol: Optional[str]) -> Optional[CompanyProfile]:
        if not symbol:
            return None
        key = symbol.upper()
        if key in tried:
            return None
        tried.add(key)
        return _profile_for_symbol(symbol)

    # Step 1 — direct ticker fast path. Avoids a search roundtrip when the
    # query already looks like a symbol.
    if _looks_like_symbol(query):
        p = _try_symbol(query.upper())
        if p is not None:
            return p

    # Step 2 — hand it to the core resolver. It handles ISIN, name search,
    # and exchange-suffix permutations in one go.
    symbol = _resolve_via_core(query)
    p = _try_symbol(symbol)
    if p is not None:
        return p

    # Step 3 — fallback Yahoo search using the raw query. Catches short or
    # abbreviated queries that neither the direct ticker nor the core
    # resolver saw (e.g. "F3").
    for candidate in _yahoo_search_symbols(query):
        p = _try_symbol(candidate)
        if p is not None:
            return p

    # Step 4 — name-based fallback. If Yahoo gave us a NAME for the original
    # symbol but no sector, search for that name and try the alternate
    # symbols it returns.
    name = _name_for_symbol(query.upper()) if _looks_like_symbol(query) else None
    if name:
        for candidate in _yahoo_search_symbols(name):
            p = _try_symbol(candidate)
            if p is not None:
                return p

    # Step 5 — exchange-suffix stripping. When the query is ``STM.MI`` and
    # that exact symbol has no Yahoo data, search for the base ticker
    # ``STM`` — which typically returns siblings on other exchanges
    # (``STMMI.MI``, ``STMPA.PA``, ``STM`` on NYSE) that DO have sector
    # data. The core resolver bails out early when a dot is present, so
    # this step fills that gap.
    #
    # Disabled for junior-market suffixes (TSXV ``.V``, CSE ``.CN``):
    # a missing listing there is far more likely to be genuinely dead
    # than to have an alternate sibling on a major exchange. Stripping
    # ``PGM.V`` (TSXV palladium junior) to ``PGM`` and picking a US
    # publishing company would be actively wrong.
    if ("." in query or "-" in query) and not _is_junior_market_suffix(query):
        base = re.split(r"[.\-]", query, 1)[0]
        if base and base.upper() not in tried:
            for candidate in _yahoo_search_symbols(base):
                p = _try_symbol(candidate)
                if p is not None:
                    return p

    return None


_JUNIOR_SUFFIXES = (".V", ".CN", ".NE", ".NEO", ".BO")


def _is_junior_market_suffix(query: str) -> bool:
    upper = query.upper()
    return any(upper.endswith(s) for s in _JUNIOR_SUFFIXES)


_SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,6}([-.][A-Za-z0-9]{1,4})*$")


def _looks_like_symbol(query: str) -> bool:
    """Conservative: letters/digits + optional single '.' or '-' chunk.

    Matches ``AAPL``, ``BRK-B``, ``OCO.V``, ``005930.KS`` (and their
    lowercase equivalents); rejects anything with spaces, punctuation, or
    longer than a realistic symbol.

    Mixed-case strings like ``Apple`` are rejected — real tickers are
    always rendered in a single case in data feeds, so the mixed-case
    form is far more likely to be a company name the user typed.
    """
    if " " in query or len(query) > 12 or not query:
        return False
    # All-upper or all-lower only; "Apple" gets sent to the resolver.
    if query != query.upper() and query != query.lower():
        return False
    return bool(_SYMBOL_RE.match(query))


def _profile_for_symbol(symbol: str) -> Optional[CompanyProfile]:
    """Fetch yfinance ``Ticker(symbol).info`` and map it into CompanyProfile."""
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return None
    with _silence_stdio():
        try:
            info = getattr(yf.Ticker(symbol), "info", None) or {}
        except Exception:
            return None
    if not info:
        return None
    sector = info.get("sector") or info.get("sectorKey")
    industry = info.get("industry") or info.get("industryKey")
    description = info.get("longBusinessSummary") or info.get("summaryProfile", "") or ""
    # Reject profiles with *no* classification data — they're almost always
    # delisted shells or pink-sheet entities yfinance couldn't enrich.
    if not (sector or industry or description):
        return None
    name = info.get("longName") or info.get("shortName") or symbol
    resolved_symbol = info.get("symbol") or symbol
    return CompanyProfile(
        ticker=resolved_symbol.upper(),
        name=name,
        sector=sector,
        industry=industry,
        description=description,
        source="yfinance",
    )


def _resolve_via_core(query: str) -> Optional[str]:
    """Use ``lynx_investor_core.ticker.resolve_identifier`` to turn *query*
    (name / ISIN / bare ticker) into a canonical symbol. Returns None on any
    failure — the caller then tries the next resolution strategy."""
    try:
        from lynx_investor_core.ticker import resolve_identifier
    except Exception:
        return None
    with _silence_stdio():
        try:
            symbol, _isin = resolve_identifier(query)
        except ValueError:
            return None
        except Exception:
            return None
    return symbol


def _yahoo_search_first_equity(query: str) -> Optional[str]:
    """First equity symbol from a Yahoo symbol search (legacy single-result API)."""
    for symbol in _yahoo_search_symbols(query):
        return symbol
    return None


def _yahoo_search_symbols(query: str) -> List[str]:
    """Return EQUITY-first ranked list of symbols for *query*.

    Iterating the full list (not just the top hit) matters for names like
    "STMicroelectronics" where the top result can be an exchange-specific
    variant that lacks sector data while another variant on the same list
    has it. Also: equities first, then anything else — so we avoid
    returning a mutual fund or ETF when a real stock exists.
    """
    try:
        from lynx_investor_core.ticker import search_companies
    except Exception:
        return []
    with _silence_stdio():
        try:
            results = search_companies(query, max_results=15)
        except Exception:
            return []
    equities = [r.symbol for r in results if r.quote_type == "EQUITY" and r.symbol]
    rest = [r.symbol for r in results if r.symbol and r.quote_type != "EQUITY"]
    # Deduplicate while preserving order.
    seen: set = set()
    ordered: List[str] = []
    for symbol in [*equities, *rest]:
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    return ordered


def _name_for_symbol(symbol: str) -> Optional[str]:
    """Fetch the company name for *symbol* without requiring sector data.

    Used as a pivot when the original symbol's full profile is missing but
    Yahoo does know the name — we then re-search by name to find an
    alternate symbol (often a different exchange listing) that carries the
    full profile.
    """
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return None
    with _silence_stdio():
        try:
            info = getattr(yf.Ticker(symbol), "info", None) or {}
        except Exception:
            return None
    name = info.get("longName") or info.get("shortName")
    if name and isinstance(name, str) and name != symbol:
        return name
    return None


@contextlib.contextmanager
def _silence_stdio():
    """Temporarily redirect stdout/stderr to a bit bucket.

    yfinance and Rich both spray diagnostic output while they work. That's
    fine in a CLI tool but it leaks into the GUI/TUI dashboards. Swallowing
    it here keeps the dashboard quiet.

    When ``LYNX_DEBUG=1`` is set we become a no-op so developers see the
    underlying diagnostics. The file handle is owned by an ExitStack so
    it always closes — even if the redirect or the wrapped block raises.
    """
    if os.environ.get("LYNX_DEBUG", "").strip() in {"1", "true", "TRUE", "yes"}:
        yield
        return
    with contextlib.ExitStack() as stack:
        devnull = stack.enter_context(open(os.devnull, "w"))
        stack.enter_context(contextlib.redirect_stdout(devnull))
        stack.enter_context(contextlib.redirect_stderr(devnull))
        yield


# ---------------------------------------------------------------------------
# Offline heuristic (used when yfinance unavailable)
# ---------------------------------------------------------------------------

# Well-known tickers → sector registry name. Intentionally tiny — enough for
# demo / offline use; yfinance is the real source of truth.
_OFFLINE_TICKER_HINTS: Tuple[Tuple[str, str], ...] = (
    # Energy
    ("XOM", "lynx-investor-energy"),
    ("CVX", "lynx-investor-energy"),
    ("SHEL", "lynx-investor-energy"),
    ("BP", "lynx-investor-energy"),
    ("TTE", "lynx-investor-energy"),
    ("COP", "lynx-investor-energy"),
    ("EOG", "lynx-investor-energy"),
    ("SLB", "lynx-investor-energy"),
    # Financials
    ("JPM", "lynx-investor-financials"),
    ("BAC", "lynx-investor-financials"),
    ("WFC", "lynx-investor-financials"),
    ("C", "lynx-investor-financials"),
    ("GS", "lynx-investor-financials"),
    ("MS", "lynx-investor-financials"),
    ("BRK-B", "lynx-investor-financials"),
    ("V", "lynx-investor-financials"),
    ("MA", "lynx-investor-financials"),
    ("AXP", "lynx-investor-financials"),
    # Tech
    ("AAPL", "lynx-investor-information-technology"),
    ("MSFT", "lynx-investor-information-technology"),
    ("NVDA", "lynx-investor-information-technology"),
    ("AMD", "lynx-investor-information-technology"),
    ("TSM", "lynx-investor-information-technology"),
    ("INTC", "lynx-investor-information-technology"),
    ("ORCL", "lynx-investor-information-technology"),
    ("CRM", "lynx-investor-information-technology"),
    ("ADBE", "lynx-investor-information-technology"),
    # Healthcare
    ("JNJ", "lynx-investor-healthcare"),
    ("PFE", "lynx-investor-healthcare"),
    ("UNH", "lynx-investor-healthcare"),
    ("MRK", "lynx-investor-healthcare"),
    ("LLY", "lynx-investor-healthcare"),
    ("ABBV", "lynx-investor-healthcare"),
    ("MRNA", "lynx-investor-healthcare"),
    ("GILD", "lynx-investor-healthcare"),
    # Basic Materials
    ("NEM", "lynx-investor-basic-materials"),
    ("FCX", "lynx-investor-basic-materials"),
    ("BHP", "lynx-investor-basic-materials"),
    ("RIO", "lynx-investor-basic-materials"),
    ("GOLD", "lynx-investor-basic-materials"),
    ("OCO.V", "lynx-investor-basic-materials"),
    # Consumer Discretionary
    ("AMZN", "lynx-investor-consumer-discretionary"),
    ("TSLA", "lynx-investor-consumer-discretionary"),
    ("HD", "lynx-investor-consumer-discretionary"),
    ("NKE", "lynx-investor-consumer-discretionary"),
    ("MCD", "lynx-investor-consumer-discretionary"),
    ("SBUX", "lynx-investor-consumer-discretionary"),
    # Consumer Staples
    ("PG", "lynx-investor-consumer-staples"),
    ("KO", "lynx-investor-consumer-staples"),
    ("PEP", "lynx-investor-consumer-staples"),
    ("WMT", "lynx-investor-consumer-staples"),
    ("COST", "lynx-investor-consumer-staples"),
    ("MO", "lynx-investor-consumer-staples"),
    ("PM", "lynx-investor-consumer-staples"),
    # Industrials
    ("BA", "lynx-investor-industrials"),
    ("CAT", "lynx-investor-industrials"),
    ("GE", "lynx-investor-industrials"),
    ("UNP", "lynx-investor-industrials"),
    ("HON", "lynx-investor-industrials"),
    ("LMT", "lynx-investor-industrials"),
    ("RTX", "lynx-investor-industrials"),
    # Utilities
    ("NEE", "lynx-investor-utilities"),
    ("DUK", "lynx-investor-utilities"),
    ("SO", "lynx-investor-utilities"),
    ("AEP", "lynx-investor-utilities"),
    ("D", "lynx-investor-utilities"),
    # Comm services
    ("GOOGL", "lynx-investor-communication-services"),
    ("GOOG", "lynx-investor-communication-services"),
    ("META", "lynx-investor-communication-services"),
    ("NFLX", "lynx-investor-communication-services"),
    ("DIS", "lynx-investor-communication-services"),
    ("T", "lynx-investor-communication-services"),
    ("VZ", "lynx-investor-communication-services"),
    # Real estate
    ("PLD", "lynx-investor-real-estate"),
    ("AMT", "lynx-investor-real-estate"),
    ("SPG", "lynx-investor-real-estate"),
    ("O", "lynx-investor-real-estate"),
    ("EQIX", "lynx-investor-real-estate"),
)


def _offline_profile(query: str) -> CompanyProfile:
    """Build a best-effort profile from *query* without hitting the network."""
    q = query.strip()
    q_upper = q.upper()
    for ticker, registry_name in _OFFLINE_TICKER_HINTS:
        if q_upper == ticker:
            entry = _find_registry_entry(registry_name)
            if entry is None:
                continue
            # Use sector only — sectors are disjoint across agents, whereas
            # some industries (e.g. "uranium") appear in several entries'
            # industry lists and would cause ambiguous ranking.
            return CompanyProfile(
                ticker=q_upper,
                name=q,
                sector=_pick_unique_sector(entry),
                industry=None,
                description="",
                source="offline",
            )
    # Name-based heuristic: scan description patterns
    q_lower = q.lower()
    for entry in AGENT_REGISTRY:
        for pattern in entry.description_patterns:
            if re.search(pattern, q_lower):
                return CompanyProfile(
                    ticker=_ticker_like(q_upper),
                    name=q,
                    sector=_pick_unique_sector(entry),
                    industry=None,
                    description=q,
                    source="offline",
                )
    return CompanyProfile(ticker=_ticker_like(q_upper), name=q, source="offline")


def _ticker_like(query: str) -> str:
    """Return *query* uppercased if it looks like a ticker/ISIN, else ''.

    Permissive on purpose: allows letters, digits, dot, and dash so real
    symbols like ``BRK-B`` and ``OCO.V`` round-trip, but arbitrary free-text
    doesn't leak into the ticker slot.
    """
    if not query:
        return ""
    return query if all(ch.isalnum() or ch in ".-" for ch in query) else ""


def _pick_unique_sector(entry: AgentEntry) -> Optional[str]:
    """Return a sector string from *entry* that is disjoint from every other
    entry — deterministic and unambiguous for ranking."""
    others = set().union(*(e.sectors for e in AGENT_REGISTRY if e is not entry))
    for sector in sorted(entry.sectors):
        if sector not in others:
            return sector
    return next(iter(sorted(entry.sectors)), None)


def _find_registry_entry(name: str) -> Optional[AgentEntry]:
    for entry in AGENT_REGISTRY:
        if entry.name == name:
            return entry
    return None


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def _rank_agents(profile: CompanyProfile) -> List[Launchable]:
    """Rank agents by how *strongly* they match *profile*, strong → weak.

    The core ``AGENT_REGISTRY`` returns the first match in registry order,
    but a description-pattern hit shouldn't outrank a sector hit. Example:
    Procter & Gamble's Yahoo sector is "Consumer Defensive" (staples) but
    its long description includes "e-commerce channels", which hits
    consumer-discretionary's description pattern. Without priority
    scoring, the first-match-wins rule would recommend the wrong agent.

    Scoring (higher wins, registry order breaks ties):
      * sector match        = 100
      * industry match      = 50
      * description match   = 10
    """
    scored: List[Tuple[int, int, Launchable]] = []
    sector = (profile.sector or "").lower().strip()
    industry = (profile.industry or "").lower().strip()
    description = (profile.description or "").lower()

    for idx, entry in enumerate(AGENT_REGISTRY):
        score = 0
        if sector and sector in entry.sectors:
            score += 100
        if industry:
            for allowed in entry.industries:
                if allowed in industry or industry in allowed:
                    score += 50
                    break
        if description and entry.description_patterns:
            if any(re.search(p, description) for p in entry.description_patterns):
                score += 10
        if score <= 0:
            continue
        item = by_registry_name(entry.name)
        if item is None:
            continue
        # Sort key: higher score first; lower registry index first on ties.
        scored.append((-score, idx, item))

    scored.sort()
    # De-dup while preserving order (different entries can't map to the same
    # dashboard Launchable, so this is belt-and-suspenders).
    seen: List[Launchable] = []
    for _, _, item in scored:
        if item not in seen:
            seen.append(item)
    return seen


def _explain(profile: CompanyProfile, primary: Optional[Launchable]) -> str:
    if primary is None:
        return (
            "No sector match. Try one of the three core apps (Fundamental, "
            "Compare, Portfolio) or enter a different ticker."
        )
    bits = []
    if profile.sector:
        bits.append(f"sector = {profile.sector}")
    if profile.industry:
        bits.append(f"industry = {profile.industry}")
    if not bits and profile.description:
        bits.append("description keywords")
    source = "Yahoo Finance" if profile.source == "yfinance" else "offline hint table"
    why = ", ".join(bits) if bits else "ticker heuristic"
    return f"Matched via {source} ({why})."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recommend_for_profile(profile: CompanyProfile, query: str = "") -> Recommendation:
    ranked = _rank_agents(profile)
    primary = ranked[0] if ranked else None
    alternates = ranked[1:] if len(ranked) > 1 else []
    return Recommendation(
        query=query or profile.ticker or profile.name,
        profile=profile,
        primary=primary,
        alternates=alternates,
        reason=_explain(profile, primary),
    )


def recommend_for_query(query: str, *, use_network: bool = True) -> Recommendation:
    """Recommend agents for a ticker / ISIN / company name *query*.

    ``use_network=False`` skips the yfinance lookup and relies only on the
    offline ticker hint table. Tests and the ``--offline`` CLI switch pass
    ``False`` here.
    """
    query = (query or "").strip()
    if not query:
        return Recommendation(
            query="",
            profile=CompanyProfile(),
            reason="No query provided.",
        )
    profile: Optional[CompanyProfile] = None
    if use_network:
        profile = _fetch_yf_profile(query)
    if profile is None:
        profile = _offline_profile(query)
    return recommend_for_profile(profile, query=query)
