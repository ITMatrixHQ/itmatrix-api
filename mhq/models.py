from __future__ import annotations

from typing import Generic, TypeVar

import msgspec

T = TypeVar("T")


class CamelStruct(msgspec.Struct, rename="camel"):
    """Base model for public API payloads that use camelCase JSON fields."""


class PublicEnvelope(CamelStruct, Generic[T]):
    """Standard `/api/v1` response wrapper."""

    status: str
    request_id: str | None = None
    results: T | None = None
    count: int | None = None
    error: str | None = None
    retry_after_ms: int | None = None


class ErrorPayload(CamelStruct):
    """Non-envelope middleware error payload."""

    error: str
    retry_after_ms: int | None = None


class Expirations(CamelStruct):
    """Available option expirations for a symbol."""

    symbol: str
    expirations: list[str]


class Spot(CamelStruct):
    """Latest underlying price result."""

    symbol: str
    price: float
    updated_at: str


class OptionQuote(CamelStruct):
    """Current option quote, greeks, and underlying context."""

    ticker: str
    underlying: str
    expiration: str
    strike: float
    contract_type: str
    fmv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    open_interest: int | None = None
    day_volume: int | None = None
    underlying_price: float | None = None
    updated_at: str | None = None


class GexTotals(CamelStruct):
    """Aggregated GEX totals."""

    total_gex_shares: float = 0.0
    total_gex_dollars: float = 0.0
    total_gex_delta_adj_shares: float = 0.0
    total_gex_delta_adj_dollars: float = 0.0


class GexStrike(CamelStruct):
    """GEX metrics for a single strike."""

    total_gex_shares: float = 0.0
    total_gex_dollars: float = 0.0
    total_gex_delta_adj_shares: float = 0.0
    total_gex_delta_adj_dollars: float = 0.0
    call_ticker: str | None = None
    put_ticker: str | None = None


class GexResult(CamelStruct):
    """Current or historical GEX grid for one expiration."""

    symbol: str
    expiration: str
    spot_price: float | None = None
    updated_at: str | None = None
    net_gex: GexTotals | None = None
    max_abs_gex: GexTotals | None = None
    zero_gamma_level: float | None = None
    strikes: list[float] = msgspec.field(default_factory=list)
    gex_by_strike: dict[str, GexStrike] = msgspec.field(default_factory=dict)


class GexMatrix(CamelStruct):
    """GEX grid collection across expirations."""

    symbol: str
    expirations: list[GexResult]
    captured_at: str | None = None


class GexHistorySnapshot(CamelStruct):
    """Intraday GEX snapshot summary."""

    captured_at: str
    spot_price: float | None = None
    net_gex: GexTotals | None = None


class GexHistory(CamelStruct):
    """Intraday GEX history for a symbol and date."""

    symbol: str
    date: str
    snapshots: list[GexHistorySnapshot]


class PricePoint(msgspec.Struct):
    """Smoothed price point returned by stock and option bar routes."""

    t: int
    price: float


class RatioRow(msgspec.Struct):
    """Fundamentals ratio row."""

    ticker: str
    date: str
    price: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    avg_volume: float | None = None
    pe: float | None = None
    pb: float | None = None
    ps: float | None = None
    pcf: float | None = None
    pfcf: float | None = None
    ev_sales: float | None = None
    ev_ebitda: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    roe: float | None = None
    roa: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    cash_ratio: float | None = None
    free_cash_flow: float | None = None
    updated_at: str | None = None


class IncomeRow(msgspec.Struct):
    """Fundamentals income statement row."""

    ticker: str
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    timeframe: str | None = None
    period_end: str | None = None
    filing_date: str | None = None
    revenue: float | None = None
    cost_of_revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    diluted_eps: float | None = None
    basic_eps: float | None = None
    ebitda: float | None = None
    income_taxes: float | None = None
    updated_at: str | None = None


class BalanceSheetRow(msgspec.Struct):
    """Fundamentals balance sheet row."""

    ticker: str
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    timeframe: str | None = None
    period_end: str | None = None
    filing_date: str | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    cash_and_equivalents: float | None = None
    total_current_assets: float | None = None
    total_current_liabilities: float | None = None
    long_term_debt: float | None = None
    goodwill: float | None = None
    retained_earnings: float | None = None
    updated_at: str | None = None


class CashFlowRow(msgspec.Struct):
    """Fundamentals cash flow row."""

    ticker: str
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    timeframe: str | None = None
    period_end: str | None = None
    filing_date: str | None = None
    net_cash_operating: float | None = None
    net_cash_investing: float | None = None
    net_cash_financing: float | None = None
    capex: float | None = None
    depreciation: float | None = None
    dividends_paid: float | None = None
    updated_at: str | None = None


class DividendRow(msgspec.Struct):
    """Fundamentals dividend row."""

    ticker: str
    ex_dividend_date: str | None = None
    cash_amount: float | None = None
    currency: str | None = None
    frequency: int | None = None
    declaration_date: str | None = None
    record_date: str | None = None
    pay_date: str | None = None
    distribution_type: str | None = None
    updated_at: str | None = None


class SplitRow(msgspec.Struct):
    """Fundamentals split row."""

    ticker: str
    execution_date: str | None = None
    split_from: float | None = None
    split_to: float | None = None
    adjustment_type: str | None = None
    updated_at: str | None = None


class ShortInterestRow(msgspec.Struct):
    """Fundamentals short interest row."""

    ticker: str
    settlement_date: str | None = None
    short_interest: float | None = None
    avg_daily_volume: float | None = None
    days_to_cover: float | None = None
    updated_at: str | None = None


class FloatRow(msgspec.Struct):
    """Fundamentals float row."""

    ticker: str
    free_float: float | None = None
    free_float_percent: float | None = None
    effective_date: str | None = None
    updated_at: str | None = None


class NewsRow(msgspec.Struct):
    """Fundamentals news row."""

    id: str
    title: str | None = None
    description: str | None = None
    article_url: str | None = None
    author: str | None = None
    published_utc: str | None = None
    tickers: list[str] | None = None
    keywords: list[str] | None = None
    publisher_name: str | None = None
    sentiment: str | None = None
    source: str | None = None
    updated_at: str | None = None


class TreasuryYieldRow(msgspec.Struct):
    """Treasury yield economy row."""

    date: str
    y1m: float | None = None
    y3m: float | None = None
    y6m: float | None = None
    y1y: float | None = None
    y2y: float | None = None
    y3y: float | None = None
    y5y: float | None = None
    y7y: float | None = None
    y10y: float | None = None
    y20y: float | None = None
    y30y: float | None = None


class InflationRow(msgspec.Struct):
    """Inflation economy row."""

    date: str
    cpi: float | None = None
    cpi_core: float | None = None
    cpi_yoy: float | None = None
    pce: float | None = None
    pce_core: float | None = None
    pce_spending: float | None = None


class LaborRow(msgspec.Struct):
    """Labor economy row."""

    date: str
    unemployment_rate: float | None = None
    participation_rate: float | None = None
    avg_hourly_earnings: float | None = None
    job_openings: float | None = None


class WsEvent(CamelStruct):
    """Typed WebSocket event returned by subscription iterators."""

    channel: str
    symbol: str
    data: GexMatrix | None = None
    expiration: str | None = None
    strike: float | None = None
    gex_shares: float | None = None
    gex_dollars: float | None = None
    delta_adj_shares: float | None = None
    delta_adj_dollars: float | None = None
    price: float | None = None
    fmv: float | None = None
    t: int | None = None
    type: str | None = None
