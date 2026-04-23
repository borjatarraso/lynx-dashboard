"""Catalog of every launchable app and agent in the Lince Investor Suite.

The registry is the single source of truth for the dashboard: it knows every
entry's display name, short description, CLI command, which UI modes are
supported, which keybinding jumps to it, and which sector-registry name it
maps to (for agents — used by the company → agent recommender).

Each entry is a frozen dataclass so the registry is safe to import at module
load time. No I/O happens here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Tuple

__all__ = [
    "LaunchableKind",
    "Launchable",
    "APPS",
    "AGENTS",
    "ALL_LAUNCHABLES",
    "by_name",
    "by_keybinding",
    "by_registry_name",
    "apps_for_mode",
    "agents_for_mode",
]


class LaunchableKind:
    APP = "app"
    AGENT = "agent"


@dataclass(frozen=True)
class Launchable:
    """A single launchable program (either a core app or a sector agent)."""

    name: str                               # human-friendly name shown in UI
    short_name: str                         # 1-3 word tag for buttons
    kind: str                               # LaunchableKind.APP / AGENT
    command: str                            # CLI executable (lynx-fundamental, lynx-energy, ...)
    package: str                            # installed package name (lynx_fundamental, lynx_energy, ...)
    tagline: str                            # one-line pitch
    description: str                        # multi-line description
    category: str                           # "Core" / a GICS sector / "Tools"
    modes: FrozenSet[str] = field(default_factory=frozenset)   # {"console","interactive","tui","gui"}
    keybinding: Optional[str] = None        # textual binding ("f", "1", "ctrl+f", etc.)
    registry_name: Optional[str] = None     # matches AgentEntry.name in sector_registry (agents only)
    example_tickers: Tuple[str, ...] = ()   # example tickers the user can try
    color: str = "cyan"                     # Rich style color used in panels/buttons

    # Extended detail shown in the Info dialog.
    details: str = ""                       # multi-paragraph deeper description
    data_sources: Tuple[str, ...] = ()      # what data sources / APIs are used
    specialization: str = ""                # for agents: what makes this one unique

    @property
    def is_app(self) -> bool:
        return self.kind == LaunchableKind.APP

    @property
    def is_agent(self) -> bool:
        return self.kind == LaunchableKind.AGENT

    def supports(self, mode: str) -> bool:
        return mode in self.modes


_ALL_MODES = frozenset({"console", "interactive", "tui", "gui"})
_NO_GUI_MODES = frozenset({"console", "interactive", "tui"})
_CLI_MODES = frozenset({"console", "interactive"})


# ---------------------------------------------------------------------------
# Core apps
# ---------------------------------------------------------------------------

APPS: Tuple[Launchable, ...] = (
    Launchable(
        name="Lynx Fundamental",
        short_name="Fundamental",
        kind=LaunchableKind.APP,
        command="lynx-fundamental",
        package="lynx",
        tagline="Value investing + moat analysis for any public company",
        description=(
            "Full-stack fundamental analysis: 40+ value-investing metrics, "
            "moat scoring, intrinsic value via DCF / Graham / NCAV / Peter Lynch, "
            "SEC filings and recent news. Works on any publicly-traded company "
            "by ticker, ISIN, or company name."
        ),
        category="Core",
        modes=_ALL_MODES,
        keybinding="f",
        example_tickers=("AAPL", "MSFT", "GOOGL", "OCO.V"),
        color="blue",
        details=(
            "Fetches up to five years of financial statements, computes 40+ "
            "value-investing metrics (Piotroski F-Score, Altman Z-Score, ROIC, "
            "Graham Number, FCF yield, interest coverage, Beneish M-Score…), "
            "runs a structured moat analysis across ten moat dimensions, and "
            "produces four independent intrinsic-value estimates (DCF, Graham, "
            "NCAV, Peter Lynch) with a reconciled range.\n\n"
            "Downloads recent SEC/SEDAR filings and top-ranked news for "
            "context, then renders one consolidated report. Caches per-ticker "
            "so repeat analyses are instant; --refresh forces a re-pull."
        ),
        data_sources=(
            "yfinance — prices, financial statements, analyst estimates",
            "SEC EDGAR — US filings (10-K, 10-Q, 8-K)",
            "SEDAR+ — Canadian filings (TSX / TSXV)",
            "Yahoo Finance RSS + Google News RSS — company-level news",
        ),
    ),
    Launchable(
        name="Lynx Compare",
        short_name="Compare",
        kind=LaunchableKind.APP,
        command="lynx-compare",
        package="lynx_compare",
        tagline="Side-by-side comparison of two companies across every lens",
        description=(
            "Compare two companies side-by-side across valuation, profitability, "
            "solvency, growth, efficiency, moat, and intrinsic-value signals. "
            "Useful for head-to-head analysis and sanity-checking relative value."
        ),
        category="Core",
        modes=_ALL_MODES,
        keybinding="c",
        example_tickers=("AAPL MSFT", "KO PEP", "V MA"),
        color="magenta",
        details=(
            "Runs the fundamental pipeline on two companies in one pass and "
            "produces a side-by-side scorecard across valuation, profitability, "
            "solvency, growth, efficiency, moat, and intrinsic value. Each "
            "lens has a 'winner' tag so the relative-value answer is visible "
            "at a glance.\n\n"
            "Ships with a Flask REST API (lynx-compare-server) for "
            "integrating the comparison engine into external dashboards."
        ),
        data_sources=(
            "yfinance — prices + statements for both companies",
            "SEC EDGAR + SEDAR+ — recent filings for context",
            "News RSS — combined news feed for both tickers",
        ),
    ),
    Launchable(
        name="Lynx Portfolio",
        short_name="Portfolio",
        kind=LaunchableKind.APP,
        command="lynx-portfolio",
        package="lynx_portfolio",
        tagline="Multi-currency portfolio tracker with encrypted vault",
        description=(
            "Track a real portfolio across currencies, with live market data, "
            "EUR conversion, encrypted vault, first-run wizard, and CSV/JSON "
            "import/export. Runs as a REST API server too."
        ),
        category="Core",
        modes=_ALL_MODES,
        keybinding="p",
        example_tickers=(),
        color="green",
        details=(
            "Tracks a real multi-currency portfolio with live quotes, "
            "automatic EUR/USD conversion via ECB FX rates, and a locally-"
            "encrypted vault (Fernet) so credentials and positions never "
            "leave your machine.\n\n"
            "Includes a first-run wizard, CSV/JSON import & export, historical "
            "performance snapshots, REST API for dashboards, and a companion "
            "Kivy mobile client that shares the same database format."
        ),
        data_sources=(
            "yfinance — live quotes and historical prices",
            "ECB — daily reference FX rates",
            "Local encrypted vault — positions, lots, transactions",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Sector-specialized agents (11 total — one per GICS sector)
# ---------------------------------------------------------------------------

AGENTS: Tuple[Launchable, ...] = (
    Launchable(
        name="Energy",
        short_name="Energy",
        kind=LaunchableKind.AGENT,
        command="lynx-energy",
        package="lynx_energy",
        tagline="Oil, gas, pipelines, LNG, energy services",
        description=(
            "Specialized analysis for the energy sector: reserves, production, "
            "breakeven prices, midstream throughput, refining margins, commodity "
            "exposure, decommissioning liabilities."
        ),
        category="Energy",
        modes=_ALL_MODES,
        keybinding="1",
        registry_name="lynx-investor-energy",
        example_tickers=("XOM", "CVX", "SHEL", "TTE"),
        color="yellow",
        details=(
            "Builds on the fundamental pipeline with energy-sector specifics: "
            "reserves accounting (1P/2P/3P), breakeven WTI and Brent, "
            "decommissioning-liability posture, midstream throughput coverage, "
            "refining crack spreads, and a commodity-price sensitivity deck."
        ),
        data_sources=(
            "yfinance — financials & prices",
            "SEC filings — reserves footnotes (10-K, 20-F)",
            "Energy-sector news filters (WTI, Brent, LNG, OPEC)",
        ),
        specialization=(
            "Reserves-aware intrinsic value scales with your commodity-price "
            "deck. Flags under-/over-hedged producers and pipeline-throughput "
            "risk — details that generic fundamentals ignore."
        ),
    ),
    Launchable(
        name="Financials",
        short_name="Financials",
        kind=LaunchableKind.AGENT,
        command="lynx-finance",
        package="lynx_finance",
        tagline="Banks, insurers, asset managers, exchanges",
        description=(
            "Purpose-built for financials: NII, NIM, efficiency ratio, CET1, "
            "combined ratio, AUM fee streams, book-value-centric valuation."
        ),
        category="Financials",
        modes=_ALL_MODES,
        keybinding="2",
        registry_name="lynx-investor-financials",
        example_tickers=("JPM", "BAC", "BRK-B", "V"),
        color="green",
        details=(
            "Bank/insurer/asset-manager-aware fundamentals. Computes NII, "
            "NIM, efficiency ratio, and CET1 for banks; combined ratio, "
            "float yield, and reserve adequacy for insurers; AUM-based fee "
            "economics for asset managers. Replaces traditional valuation "
            "lenses with book-value and embedded-value frameworks."
        ),
        data_sources=(
            "yfinance — prices + regulatory line items",
            "SEC 10-K / 10-Q and Call Reports for banks",
            "Regulatory capital disclosures (CET1, Tier 1)",
        ),
        specialization=(
            "Book-value-centric intrinsic value plus regulatory-capital "
            "analysis that generic value tooling doesn't model. Treats "
            "insurers on combined ratio rather than earnings multiples."
        ),
    ),
    Launchable(
        name="Information Technology",
        short_name="Tech",
        kind=LaunchableKind.AGENT,
        command="lynx-tech",
        package="lynx_tech",
        tagline="Software, semis, cloud, hardware",
        description=(
            "Tech-focused analysis: ARR/NRR, cohort retention, gross margin "
            "trajectory, semiconductor capacity cycles, platform economics."
        ),
        category="Information Technology",
        modes=_ALL_MODES,
        keybinding="3",
        registry_name="lynx-investor-information-technology",
        example_tickers=("AAPL", "MSFT", "NVDA", "TSM"),
        color="cyan",
        details=(
            "Software-/semi-/hardware-aware fundamentals. Adds ARR, NRR, and "
            "cohort retention lenses for subscription software; capital-cycle "
            "analysis for semiconductors; platform-economics scoring for "
            "marketplaces. Rule-of-40, gross-margin trajectory, and R&D "
            "efficiency feature prominently."
        ),
        data_sources=(
            "yfinance — financials + price history",
            "SEC filings + S-1 disclosures for recent IPOs",
            "Tech-sector news: earnings, product launches",
        ),
        specialization=(
            "Subscription-software unit economics (Rule of 40, NRR) and "
            "semiconductor capital-cycle indicators — the things that "
            "actually drive tech valuations."
        ),
    ),
    Launchable(
        name="Healthcare",
        short_name="Healthcare",
        kind=LaunchableKind.AGENT,
        command="lynx-health",
        package="lynx_health",
        tagline="Pharma, biotech, devices, care providers",
        description=(
            "Healthcare specialization: pipeline stage gates, patent cliffs, "
            "clinical-trial milestones, payer mix, device reimbursement dynamics."
        ),
        category="Healthcare",
        modes=_ALL_MODES,
        keybinding="4",
        registry_name="lynx-investor-healthcare",
        example_tickers=("JNJ", "PFE", "UNH", "MRNA"),
        color="red",
        details=(
            "Pharma/biotech/device/provider-aware analysis. Scores pipeline "
            "depth and stage gates, flags approaching patent cliffs, tracks "
            "clinical-trial milestones (Phase I/II/III), and distinguishes "
            "payer-mix dynamics between providers, insurers, and pharma."
        ),
        data_sources=(
            "yfinance — financials and analyst data",
            "SEC 10-K plus ClinicalTrials.gov references pulled from news",
            "Healthcare-sector news: FDA, EMA, trial readouts",
        ),
        specialization=(
            "Clinical-pipeline valuation and patent-cliff exposure — both "
            "invisible in generic fundamentals — combined with payer-mix "
            "aware analysis for providers and insurers."
        ),
    ),
    Launchable(
        name="Basic Materials",
        short_name="Materials",
        kind=LaunchableKind.AGENT,
        command="lynx-mining",
        package="lynx_mining",
        tagline="Mining, metals, commodities, chemicals",
        description=(
            "Mining- & materials-aware analysis: NI 43-101 / JORC resources, "
            "AISC, byproduct credits, smelter economics, commodity price decks."
        ),
        category="Basic Materials",
        modes=_ALL_MODES,
        keybinding="5",
        registry_name="lynx-investor-basic-materials",
        example_tickers=("NEM", "FCX", "BHP", "RIO"),
        color="yellow",
        details=(
            "Mining-, metals-, and chemicals-aware. Parses NI 43-101 / JORC "
            "mineral-resource disclosures, computes AISC (all-in sustaining "
            "cost), tracks byproduct credits and smelter economics, and runs "
            "the intrinsic-value model against a commodity price deck rather "
            "than the single-number assumption in generic DCF."
        ),
        data_sources=(
            "yfinance — financials + price history",
            "NI 43-101 / JORC resource reports",
            "Metals & mining news (LME, gold, copper, uranium)",
        ),
        specialization=(
            "Resource-based (NI 43-101 / JORC) valuation, AISC benchmarking, "
            "and byproduct-credit accounting — domain-specific accounting "
            "that generic fundamentals can't produce."
        ),
    ),
    Launchable(
        name="Consumer Discretionary",
        short_name="Cyclical",
        kind=LaunchableKind.AGENT,
        command="lynx-discretionary",
        package="lynx_discretionary",
        tagline="Autos, retail, luxury, travel, leisure",
        description=(
            "Consumer-cyclical analysis: same-store sales, inventory turns, "
            "brand strength, discretionary spending beta, channel mix."
        ),
        category="Consumer Discretionary",
        modes=_ALL_MODES,
        keybinding="6",
        registry_name="lynx-investor-consumer-discretionary",
        example_tickers=("AMZN", "TSLA", "HD", "NKE"),
        color="magenta",
        details=(
            "Consumer-cyclical analysis: same-store-sales growth, inventory "
            "turns, brand strength, channel mix, discretionary-spending "
            "beta. Weighs retail vs. luxury vs. travel vs. auto sub-segments "
            "differently so a luxury house and a mass retailer are valued "
            "on their own merits."
        ),
        data_sources=(
            "yfinance",
            "SEC filings + 10-K segment data",
            "Consumer & retail news (foot traffic, same-store sales)",
        ),
        specialization=(
            "Same-store-sales / cohort analysis and sub-segment-aware "
            "valuation across auto, retail, luxury, and leisure."
        ),
    ),
    Launchable(
        name="Consumer Staples",
        short_name="Staples",
        kind=LaunchableKind.AGENT,
        command="lynx-staples",
        package="lynx_staples",
        tagline="Food, beverages, household, tobacco, grocery",
        description=(
            "Staples specialization: pricing power, volume/mix analysis, brand "
            "moat, private-label pressure, emerging-market growth."
        ),
        category="Consumer Staples",
        modes=_ALL_MODES,
        keybinding="7",
        registry_name="lynx-investor-consumer-staples",
        example_tickers=("PG", "KO", "PEP", "WMT"),
        color="green",
        details=(
            "Pricing power, volume/mix analysis, brand-moat scoring, "
            "private-label pressure, emerging-market growth. Treats a "
            "packaged-foods CPG and a grocery retailer very differently "
            "even though both sit under 'consumer defensive'."
        ),
        data_sources=(
            "yfinance",
            "SEC filings + segment disclosures",
            "CPG / retail news (Nielsen trends, commodity input costs)",
        ),
        specialization=(
            "Pricing-power and volume/mix decomposition — where CPG moats "
            "actually show up in the numbers."
        ),
    ),
    Launchable(
        name="Industrials",
        short_name="Industrials",
        kind=LaunchableKind.AGENT,
        command="lynx-industrials",
        package="lynx_industrials",
        tagline="Aerospace, machinery, freight, defense",
        description=(
            "Industrial-focused analysis: backlog/book-to-bill, aftermarket mix, "
            "defense program visibility, cyclical margin leverage, freight rates."
        ),
        category="Industrials",
        modes=_ALL_MODES,
        keybinding="8",
        registry_name="lynx-investor-industrials",
        example_tickers=("BA", "CAT", "GE", "UNP"),
        color="blue",
        details=(
            "Industrial-focused analysis: backlog / book-to-bill, aftermarket "
            "mix, defense-program visibility, cyclical margin leverage, "
            "freight rates. Handles A&D contract math, machinery aftermarket "
            "economics, and freight-cycle turns distinct from generic "
            "fundamentals."
        ),
        data_sources=(
            "yfinance",
            "SEC 10-K + defense backlog disclosures",
            "Industrial & freight news (rates, capacity, orders)",
        ),
        specialization=(
            "Book-to-bill, aftermarket-mix, and defense-program visibility "
            "lenses — the real drivers of industrial valuations."
        ),
    ),
    Launchable(
        name="Utilities",
        short_name="Utilities",
        kind=LaunchableKind.AGENT,
        command="lynx-utilities",
        package="lynx_utilities",
        tagline="Electric, gas, water, renewables",
        description=(
            "Utility-grade analysis: rate base growth, allowed ROE, capex plans, "
            "regulatory lag, renewable transition capex."
        ),
        category="Utilities",
        modes=_ALL_MODES,
        keybinding="9",
        registry_name="lynx-investor-utilities",
        example_tickers=("NEE", "DUK", "SO", "AEP"),
        color="cyan",
        details=(
            "Rate-base growth, allowed ROE, capex plans, regulatory lag, "
            "and renewable-transition capex. Models utilities as regulated-"
            "return machines rather than free-market compounders, anchoring "
            "valuation on rate base and allowed returns instead of earnings "
            "multiples."
        ),
        data_sources=(
            "yfinance",
            "FERC / state PUC filings surfaced via news",
            "Utility-sector news (rate cases, capex announcements)",
        ),
        specialization=(
            "Rate-base / allowed-ROE framework for regulated utilities plus "
            "renewable-transition capex analysis and regulatory-lag scoring."
        ),
    ),
    Launchable(
        name="Communication Services",
        short_name="Comms",
        kind=LaunchableKind.AGENT,
        command="lynx-comm",
        package="lynx_comm",
        tagline="Telecom, media, internet, gaming, publishing",
        description=(
            "Communication-services analysis: ARPU, churn, content amortization, "
            "ad-revenue cycles, wireless capex, platform engagement."
        ),
        category="Communication Services",
        modes=_ALL_MODES,
        keybinding="0",
        registry_name="lynx-investor-communication-services",
        example_tickers=("GOOGL", "META", "NFLX", "T"),
        color="magenta",
        details=(
            "ARPU, churn, content amortization, ad-revenue cyclicality, "
            "wireless capex, and platform engagement. Handles telcos, "
            "ad-supported platforms, and subscription content distinctly — "
            "each on its own KPI set instead of a one-size-fits-all lens."
        ),
        data_sources=(
            "yfinance",
            "SEC filings + subscriber disclosures",
            "Telecom / media / internet news",
        ),
        specialization=(
            "ARPU and churn math plus content-amortization scheduling — "
            "KPIs generic tooling doesn't model."
        ),
    ),
    Launchable(
        name="Real Estate",
        short_name="Real Estate",
        kind=LaunchableKind.AGENT,
        command="lynx-realestate",
        package="lynx_realestate",
        tagline="REITs, property, real-estate services",
        description=(
            "Real-estate / REIT specialization: FFO / AFFO, cap rates, occupancy, "
            "rent spreads, lease durations, development pipelines."
        ),
        category="Real Estate",
        modes=_ALL_MODES,
        keybinding="minus",
        registry_name="lynx-investor-real-estate",
        example_tickers=("PLD", "AMT", "SPG", "O"),
        color="yellow",
        details=(
            "FFO / AFFO, cap rates, occupancy, rent spreads, lease "
            "durations, and development pipelines. Switches the valuation "
            "anchor from earnings to FFO and applies NAV, P/FFO, and "
            "implied cap-rate frameworks appropriate for REITs."
        ),
        data_sources=(
            "yfinance",
            "REIT 10-K + supplemental reports",
            "Real-estate news (cap rates, occupancy, transactions)",
        ),
        specialization=(
            "FFO/AFFO-centric valuation with NAV and implied-cap-rate "
            "lenses — the canonical REIT analysis framework."
        ),
    ),
)


ALL_LAUNCHABLES: Tuple[Launchable, ...] = APPS + AGENTS


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def by_name(query: str) -> Optional[Launchable]:
    """Look up a launchable by name, short name, command, package, or keybinding."""
    if not query:
        return None
    q = query.strip().lower()
    for item in ALL_LAUNCHABLES:
        if q in (
            item.name.lower(),
            item.short_name.lower(),
            item.command.lower(),
            item.package.lower(),
        ):
            return item
        if item.keybinding and item.keybinding.lower() == q:
            return item
    for item in ALL_LAUNCHABLES:
        if q in item.name.lower() or q in item.short_name.lower():
            return item
    return None


def by_keybinding(key: str) -> Optional[Launchable]:
    if not key:
        return None
    k = key.lower()
    for item in ALL_LAUNCHABLES:
        if item.keybinding and item.keybinding.lower() == k:
            return item
    return None


def by_registry_name(registry_name: str) -> Optional[Launchable]:
    for item in AGENTS:
        if item.registry_name == registry_name:
            return item
    return None


def apps_for_mode(mode: str) -> Tuple[Launchable, ...]:
    return tuple(a for a in APPS if a.supports(mode))


def agents_for_mode(mode: str) -> Tuple[Launchable, ...]:
    return tuple(a for a in AGENTS if a.supports(mode))
