from __future__ import annotations

import argparse
import html
import json
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Number = int | float

THEME_NAMES = ("control-node", "paper-terminal", "clear-macro")
BILLION = 1_000_000_000
MILLION = 1_000_000
THOUSAND = 1_000
TEN_THOUSAND = 10_000


@dataclass(frozen=True, slots=True)
class Theme:
    """Design tokens used to generate a self-contained report shell."""

    name: str
    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    positive: str
    negative: str
    warning: str
    accent: str
    accent_2: str
    font_display: str
    font_body: str
    radius: str
    shadow: str


@dataclass(frozen=True, slots=True)
class Metric:
    """Compact metric card payload."""

    label: str
    value: str
    delta: str = ""
    sentiment: str = "neutral"
    note: str = ""


@dataclass(frozen=True, slots=True)
class Level:
    """Price level annotation for level maps and key-level tables."""

    price: float
    label: str
    kind: str = "neutral"
    note: str = ""


THEMES: dict[str, Theme] = {
    "control-node": Theme(
        name="control-node",
        background="#030607",
        surface="#080c0f",
        surface_alt="#0d151b",
        text="#f4fbff",
        muted="#9cacb8",
        border="#22313a",
        positive="#32f35d",
        negative="#ff3b4f",
        warning="#ffd322",
        accent="#1398ff",
        accent_2="#00f5d4",
        font_display="'Rajdhani', 'Oswald', 'Arial Narrow', sans-serif",
        font_body="'Barlow Condensed', 'Arial Narrow', Arial, sans-serif",
        radius="14px",
        shadow="0 0 0 1px rgba(19, 152, 255, .18), 0 20px 80px rgba(0, 0, 0, .45)",
    ),
    "paper-terminal": Theme(
        name="paper-terminal",
        background="#f2efe7",
        surface="#fffaf0",
        surface_alt="#ebe3d4",
        text="#17130d",
        muted="#6e6659",
        border="#d7c8ac",
        positive="#0c7a43",
        negative="#b91f32",
        warning="#b98500",
        accent="#204e7a",
        accent_2="#946018",
        font_display="'Fraunces', Georgia, serif",
        font_body="'Aptos', 'Segoe UI', sans-serif",
        radius="18px",
        shadow="0 20px 60px rgba(71, 45, 18, .12)",
    ),
    "clear-macro": Theme(
        name="clear-macro",
        background="#07111f",
        surface="#101b2d",
        surface_alt="#14243b",
        text="#edf5ff",
        muted="#9db0c7",
        border="#263d5d",
        positive="#37d399",
        negative="#ff6b7a",
        warning="#f9c74f",
        accent="#80b7ff",
        accent_2="#a7f3d0",
        font_display="'Sora', 'Segoe UI', sans-serif",
        font_body="'IBM Plex Sans', 'Segoe UI', sans-serif",
        radius="20px",
        shadow="0 22px 70px rgba(2, 8, 23, .35)",
    ),
}


def main(argv: list[str] | None = None) -> int:
    """Generate a static HTML report from an `mhq_data.py` JSON dump."""

    args = build_parser().parse_args(argv)
    raw = json.loads(Path(args.data).read_text(encoding="utf-8"))
    output = Path(args.output)
    report = render_report_from_dump(
        raw,
        title=args.title,
        symbol=args.symbol,
        expiration=args.expiration,
        theme_name=args.theme,
        limit=args.limit,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(output.resolve())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the small report generator CLI."""

    parser = argparse.ArgumentParser(description="Generate self-contained finance report HTML from mhq_data JSON.")
    parser.add_argument("--data", required=True, help="Path to an mhq_data.py JSON output file.")
    parser.add_argument("-o", "--output", required=True, help="Output .html path.")
    parser.add_argument("--title", default="MHQ Market Structure Report")
    parser.add_argument("--symbol", help="Symbol to prefer in aggregate dumps.")
    parser.add_argument("--expiration", help="Expiration to prefer in aggregate dumps.")
    parser.add_argument("--theme", choices=THEME_NAMES, default="control-node")
    parser.add_argument("--limit", type=int, default=24, help="Maximum GEX rows to show around spot/control levels.")
    return parser


def render_report_from_dump(
    raw: Mapping[str, Any],
    *,
    title: str,
    symbol: str | None = None,
    expiration: str | None = None,
    theme_name: str = "control-node",
    limit: int = 24,
) -> str:
    """Render a complete report from either aggregate or endpoint-specific `mhq_data.py` output."""

    data = raw.get("data", raw)
    gex = pick_gex_result(data, symbol=symbol, expiration=expiration)
    spot = pick_spot(data, symbol=symbol, fallback=gex.get("spotPrice"))
    selected_symbol = str(symbol or gex.get("symbol") or spot.get("symbol") or "MARKET").upper()
    selected_expiration = str(expiration or gex.get("expiration") or "current")
    theme = THEMES[theme_name]
    levels = infer_levels(gex, spot_price=number_or_none(spot.get("price")) or number_or_none(gex.get("spotPrice")))
    body = "\n".join(
        (
            hero_block(title, selected_symbol, selected_expiration, spot, gex),
            metric_strip(default_metrics(spot, gex, levels)),
            main_market_grid(gex, spot, levels, limit=limit),
            supporting_sections(data, selected_symbol),
        ),
    )
    subtitle = "Static HTML generated from MHQ v1 JSON for agent-authored reports."
    return page(title, body, theme=theme, eyebrow=selected_symbol, subtitle=subtitle)


def page(title: str, body: str, *, theme: Theme, eyebrow: str = "", subtitle: str = "", extra_head: str = "") -> str:
    """Wrap report fragments in a full self-contained HTML document."""

    safe_title = esc(title)
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>{base_css(theme)}</style>
  {extra_head}
</head>
<body class="theme-{theme.name}">
  <main class="report-shell">
    <header class="report-header">
      <div>
        <p class="eyebrow">{esc(eyebrow)}</p>
        <h1>{safe_title}</h1>
        <p class="subtitle">{esc(subtitle)}</p>
      </div>
      <div class="generated">
        <span>Generated</span>
        <strong>{generated}</strong>
      </div>
    </header>
    {body}
  </main>
  <script>{client_script()}</script>
</body>
</html>
"""


def hero_block(title: str, symbol: str, expiration: str, spot: Mapping[str, Any], gex: Mapping[str, Any]) -> str:
    """Build the top report identity bar."""

    price = number_or_none(spot.get("price")) or number_or_none(gex.get("spotPrice"))
    net = nested_number(gex, "netGex", "totalGexDollars")
    bias = "Positive Gamma" if net >= 0 else "Negative Gamma"
    return f"""
<section class="hero-grid">
  <div class="ticker-lockup">
    <span class="ticker-symbol">{esc(symbol)}</span>
    <span class="ticker-title">{esc(title)}</span>
  </div>
  <div class="price-tape">
    <span class="price-main">{format_number(price, digits=2)}</span>
    <span class="price-note">{esc(str(spot.get("updatedAt") or gex.get("updatedAt") or "latest"))}</span>
  </div>
  <div class="control-pill">
    <span>Expiration</span>
    <strong>{esc(expiration)}</strong>
  </div>
  <div class="control-pill accent">
    <span>Trend Bias</span>
    <strong>{bias}</strong>
  </div>
</section>
"""


def metric_strip(metrics: Sequence[Metric]) -> str:
    """Render a responsive set of compact metrics."""

    cards = "\n".join(metric_card(metric) for metric in metrics)
    return f'<section class="metric-strip">{cards}</section>'


def metric_card(metric: Metric) -> str:
    """Render one metric card."""

    delta = f'<span class="metric-delta">{esc(metric.delta)}</span>' if metric.delta else ""
    note = f'<small>{esc(metric.note)}</small>' if metric.note else ""
    return f"""
<article class="metric-card sentiment-{esc(metric.sentiment)}">
  <span>{esc(metric.label)}</span>
  <strong>{esc(metric.value)}</strong>
  {delta}
  {note}
</article>
"""


def main_market_grid(gex: Mapping[str, Any], spot: Mapping[str, Any], levels: Sequence[Level], *, limit: int) -> str:
    """Render the core market-structure grid."""

    rows = gex_rows(gex)
    focused = focus_rows(
        rows,
        spot_price=number_or_none(spot.get("price")) or number_or_none(gex.get("spotPrice")),
        limit=limit,
    )
    return f"""
<section class="market-grid">
  {panel("GEX Levels", gex_bar_chart(focused), class_name="span-7")}
  {panel("Control Node", control_node_copy(gex, levels), class_name="span-5 highlight-panel")}
  {panel("Key Levels", key_level_table(levels), class_name="span-4")}
  {panel("Level Map", level_map(levels, spot_price=number_or_none(spot.get("price"))), class_name="span-4")}
  {panel("Gamma Heat", heat_grid(rows), class_name="span-4")}
  {panel("Scenario Cards", scenario_cards(levels), class_name="span-12")}
</section>
"""


def supporting_sections(data: Mapping[str, Any], symbol: str) -> str:
    """Render optional supporting market/fundamental panels when data exists."""

    stock_bars = pick_series(data, "stockBars", symbol)
    history = pick_gex_history(data, symbol)
    fundamentals = pick_fundamentals(data, symbol)
    pieces = [
        panel("Price Path", sparkline_panel(stock_bars), class_name="span-4"),
        panel("Intraday Net GEX", sparkline_panel(history), class_name="span-4"),
        panel("Fundamental Snapshot", fundamentals_table(fundamentals), class_name="span-4"),
    ]
    return f'<section class="market-grid support-grid">{"".join(pieces)}</section>'


def panel(title: str, body: str, *, class_name: str = "") -> str:
    """Wrap a component in a labelled glass panel."""

    return f"""
<article class="panel {esc(class_name)}">
  <div class="panel-title">
    <h2>{esc(title)}</h2>
    <span></span>
  </div>
  {body}
</article>
"""


def gex_bar_chart(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render horizontal positive/negative GEX bars."""

    max_abs = max((abs(as_number(row.get("value"))) for row in rows), default=1.0) or 1.0
    bars = []
    for row in rows:
        value = as_number(row.get("value"))
        width = max(2.0, abs(value) / max_abs * 100.0)
        sentiment = "positive" if value >= 0 else "negative"
        badge = "pivot" if row.get("isPivot") else sentiment
        bars.append(
            f"""
<div class="bar-row sentiment-{sentiment}">
  <span class="bar-strike">{format_number(row.get("strike"), digits=2)}</span>
  <div class="bar-track">
    <i style="width:{width:.2f}%"></i>
    <b class="badge-{badge}">{esc(str(row.get("tag", "")))}</b>
  </div>
  <span class="bar-value">{format_money(value)}</span>
</div>
""",
        )
    return f'<div class="bar-chart">{"".join(bars)}</div>'


def control_node_copy(gex: Mapping[str, Any], levels: Sequence[Level]) -> str:
    """Render short explainable control-node commentary."""

    pivot = first_level(levels, "pivot")
    zero_gamma = number_or_none(gex.get("zeroGammaLevel"))
    pivot_text = format_number(pivot.price if pivot else zero_gamma, digits=2)
    zero_text = ""
    if zero_gamma:
        zero_text = f'<li>Zero gamma reference: <strong>{format_number(zero_gamma, digits=2)}</strong></li>'
    return f"""
<div class="node-callout">
  <div class="node-target"><span></span></div>
  <h3>{pivot_text} = Control Node</h3>
  <ul>
    <li>Largest nearby gamma cluster and likely liquidity magnet.</li>
    <li>Above the node: dealer support and lower realized volatility.</li>
    <li>Below the node: acceleration risk and wider intraday ranges.</li>
    {zero_text}
  </ul>
</div>
"""


def key_level_table(levels: Sequence[Level]) -> str:
    """Render grouped key levels as a compact table."""

    rows = [
        {
            "Price": format_number(level.price, digits=2),
            "Type": level.kind.title(),
            "Read": level.label,
            "Note": level.note,
        }
        for level in levels
    ]
    return table(rows, ("Price", "Type", "Read", "Note"))


def level_map(levels: Sequence[Level], *, spot_price: float | None) -> str:
    """Render a vertical resistance/pivot/support level map."""

    if not levels:
        return '<div class="empty-state">No levels available.</div>'
    prices = [level.price for level in levels]
    if spot_price is not None:
        prices.append(spot_price)
    low = min(prices)
    high = max(prices)
    scale = max(high - low, 1.0)
    nodes = []
    for level in levels:
        bottom = (level.price - low) / scale * 100.0
        nodes.append(
            f"""
<div class="level-node level-{esc(level.kind)}" style="bottom:{bottom:.2f}%">
  <i></i><span>{format_number(level.price, digits=2)} {esc(level.label)}</span>
</div>
""",
        )
    spot_marker = ""
    if spot_price is not None:
        bottom = (spot_price - low) / scale * 100.0
        spot_marker = (
            f'<div class="spot-marker" style="bottom:{bottom:.2f}%">'
            f"Spot {format_number(spot_price, digits=2)}</div>"
        )
    return f'<div class="level-map"><div class="level-axis"></div>{"".join(nodes)}{spot_marker}</div>'


def heat_grid(rows: Sequence[Mapping[str, Any]], *, cells: int = 48) -> str:
    """Render a compact heat strip from GEX rows."""

    if not rows:
        return '<div class="empty-state">No heat data.</div>'
    sampled = rows[:cells]
    max_abs = max((abs(as_number(row.get("value"))) for row in sampled), default=1.0) or 1.0
    blocks = []
    for row in sampled:
        value = as_number(row.get("value"))
        alpha = min(1.0, abs(value) / max_abs)
        hue_class = "pos" if value >= 0 else "neg"
        label = f"{format_number(row.get('strike'), digits=2)}: {format_money(value)}"
        blocks.append(
            f'<span class="heat-cell {hue_class}" style="--heat:{alpha:.3f}" title="{esc(label)}"></span>',
        )
    heat_legend = legend(("Positive GEX", "Negative GEX", "Control / pivot"))
    return f'<div class="heat-grid">{"".join(blocks)}</div>{heat_legend}'


def scenario_cards(levels: Sequence[Level]) -> str:
    """Render bull, bear, and chop playbook cards."""

    pivot = first_level(levels, "pivot")
    resistance = first_level(levels, "resistance")
    support = first_level(levels, "support")
    pivot_text = format_number(pivot.price, digits=2) if pivot else "pivot"
    resistance_text = format_number(resistance.price, digits=2) if resistance else "next resistance"
    support_text = format_number(support.price, digits=2) if support else "next support"
    cards = (
        scenario_card(
            "Bull Case",
            "positive",
            (f"Hold above {pivot_text}", f"Reclaim {resistance_text}", "Prefer dips into support"),
        ),
        scenario_card(
            "Bear Case",
            "negative",
            (f"Lose {pivot_text}", f"Break {support_text}", "Avoid chasing late downside"),
        ),
        scenario_card(
            "Chop Play",
            "warning",
            (f"Range around {pivot_text}", "Fade failed extremes", "Reduce size in the middle"),
        ),
    )
    return f'<div class="scenario-grid">{"".join(cards)}</div>'


def scenario_card(title: str, kind: str, bullets: Sequence[str]) -> str:
    """Render one scenario card."""

    items = "".join(f"<li>{esc(item)}</li>" for item in bullets)
    return f'<div class="scenario-card sentiment-{esc(kind)}"><h3>{esc(title)}</h3><ul>{items}</ul></div>'


def sparkline_panel(series: Sequence[Mapping[str, Any]]) -> str:
    """Render a sparkline and latest value from `{t, price}` style rows."""

    values = [as_number(row.get("price", row.get("value", row.get("netGex")))) for row in series]
    if not values:
        return '<div class="empty-state">No series data.</div>'
    latest = values[-1]
    return f"""
<div class="spark-panel">
  {sparkline(values)}
  <strong>{format_number(latest, digits=2)}</strong>
</div>
"""


def sparkline(values: Sequence[Number], *, width: int = 520, height: int = 150) -> str:
    """Render a responsive SVG sparkline."""

    if not values:
        return ""
    low = min(values)
    high = max(values)
    scale = max(high - low, 1.0)
    step = width / max(len(values) - 1, 1)
    points = []
    for index, value in enumerate(values):
        x = index * step
        y = height - ((float(value) - low) / scale * (height - 18.0)) - 9.0
        points.append(f"{x:.2f},{y:.2f}")
    return f"""
<svg class="sparkline" viewBox="0 0 {width} {height}" role="img" aria-label="Sparkline">
  <polyline points="{' '.join(points)}"></polyline>
</svg>
"""


def fundamentals_table(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render a small fundamentals table using available fields."""

    if not rows:
        return '<div class="empty-state">No fundamentals loaded.</div>'
    columns = tuple(
        first_columns(
            rows,
            preferred=("ticker", "date", "price", "market_cap", "pe", "dividend_yield"),
            limit=6,
        ),
    )
    return table(rows[:6], columns)


def table(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str:
    """Render a sortable static HTML table."""

    if not rows:
        return '<div class="empty-state">No rows.</div>'
    header = "".join(f"<th>{esc(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{esc(format_cell(row.get(column)))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        '<div class="table-wrap"><table data-sortable="true">'
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


def legend(labels: Sequence[str]) -> str:
    """Render a compact legend row."""

    items = "".join(f"<span><i></i>{esc(label)}</span>" for label in labels)
    return f'<div class="legend">{items}</div>'


def default_metrics(spot: Mapping[str, Any], gex: Mapping[str, Any], levels: Sequence[Level]) -> list[Metric]:
    """Build default finance metrics from spot/GEX data."""

    price = number_or_none(spot.get("price")) or number_or_none(gex.get("spotPrice"))
    net = nested_number(gex, "netGex", "totalGexDollars")
    max_abs = nested_number(gex, "maxAbsGex", "totalGexDollars")
    zero_gamma = number_or_none(gex.get("zeroGammaLevel"))
    pivot = first_level(levels, "pivot")
    return [
        Metric("Last Price", format_number(price, digits=2), note=str(spot.get("updatedAt", ""))),
        Metric("Net GEX", format_money(net), sentiment="positive" if net >= 0 else "negative"),
        Metric("Max Abs GEX", format_money(max_abs), sentiment="neutral"),
        Metric("Zero Gamma", format_number(zero_gamma, digits=2), sentiment="warning"),
        Metric("Control Node", format_number(pivot.price if pivot else None, digits=2), sentiment="warning"),
    ]


def infer_levels(gex: Mapping[str, Any], *, spot_price: float | None) -> list[Level]:
    """Infer support, resistance, and pivot levels from GEX-by-strike values."""

    rows = sorted(gex_rows(gex), key=lambda row: abs(as_number(row.get("value"))), reverse=True)
    if not rows:
        return []
    control = rows[0]
    pivot_price = as_number(control.get("strike"))
    positive = [row for row in rows if as_number(row.get("value")) >= 0]
    negative = [row for row in rows if as_number(row.get("value")) < 0]
    supports = nearest_side_levels(negative, spot_price=spot_price, below=True, count=3)
    resistances = nearest_side_levels(positive, spot_price=spot_price, below=False, count=3)
    levels = [Level(pivot_price, "Control Node", "pivot", "Largest absolute GEX cluster")]
    levels.extend(
        Level(as_number(row["strike"]), "Resistance", "resistance", format_money(row["value"]))
        for row in resistances
    )
    levels.extend(Level(as_number(row["strike"]), "Support", "support", format_money(row["value"])) for row in supports)
    return sorted(unique_levels(levels), key=lambda level: level.price, reverse=True)


def nearest_side_levels(
    rows: Sequence[Mapping[str, Any]],
    *,
    spot_price: float | None,
    below: bool,
    count: int,
) -> list[Mapping[str, Any]]:
    """Pick nearby rows above or below spot, falling back to strongest rows."""

    if spot_price is None:
        return list(rows[:count])
    side_rows = [row for row in rows if (as_number(row.get("strike")) < spot_price) is below]
    return sorted(side_rows, key=lambda row: abs(as_number(row.get("strike")) - spot_price))[:count]


def unique_levels(levels: Iterable[Level]) -> list[Level]:
    """De-duplicate level prices while preserving first meaning."""

    seen: set[float] = set()
    unique: list[Level] = []
    for level in levels:
        key = round(level.price, 6)
        if key in seen:
            continue
        seen.add(key)
        unique.append(level)
    return unique


def gex_rows(gex: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten a `gexByStrike` mapping into chartable row dictionaries."""

    by_strike = gex.get("gexByStrike") or gex.get("gex_by_strike") or {}
    if not isinstance(by_strike, Mapping):
        return []
    rows = []
    for strike, values in by_strike.items():
        if not isinstance(values, Mapping):
            continue
        value = as_number(values.get("totalGexDollars", values.get("total_gex_dollars", 0.0)))
        rows.append({"strike": as_number(strike), "value": value, "tag": percent_tag(value)})
    return sorted(rows, key=lambda row: as_number(row["strike"]))


def focus_rows(rows: Sequence[Mapping[str, Any]], *, spot_price: float | None, limit: int) -> list[dict[str, Any]]:
    """Keep a compact band around spot while preserving the strongest absolute level."""

    if not rows:
        return []
    pivot_index = max(range(len(rows)), key=lambda index: abs(as_number(rows[index].get("value"))))
    if spot_price is None:
        center = pivot_index
    else:
        center = min(range(len(rows)), key=lambda index: abs(as_number(rows[index].get("strike")) - spot_price))
    half = max(limit // 2, 1)
    start = max(0, center - half)
    end = min(len(rows), start + limit)
    selected = [dict(row) for row in rows[start:end]]
    for row in selected:
        row["isPivot"] = as_number(row.get("strike")) == as_number(rows[pivot_index].get("strike"))
    if not any(row.get("isPivot") for row in selected):
        selected.append({**rows[pivot_index], "isPivot": True})
        selected.sort(key=lambda row: as_number(row["strike"]))
    return selected


def pick_gex_result(data: Mapping[str, Any], *, symbol: str | None, expiration: str | None) -> Mapping[str, Any]:
    """Pick one GEX result from aggregate or direct command data."""

    if "gexByStrike" in data:
        return data
    gex = data.get("gex", {})
    if isinstance(gex, Mapping):
        if symbol and isinstance(gex.get(symbol), Mapping):
            symbol_gex = gex[symbol]
        else:
            symbol_gex = next((value for value in gex.values() if isinstance(value, Mapping)), {})
        if expiration and isinstance(symbol_gex, Mapping) and isinstance(symbol_gex.get(expiration), Mapping):
            return symbol_gex[expiration]
        if isinstance(symbol_gex, Mapping):
            direct = next((value for value in symbol_gex.values() if isinstance(value, Mapping)), None)
            if direct is not None:
                return direct
            if "gexByStrike" in symbol_gex:
                return symbol_gex
    matrix = data.get("gexMatrix", {})
    if isinstance(matrix, Mapping):
        result = next((value for value in matrix.values() if isinstance(value, Mapping)), {})
        expirations = result.get("expirations") if isinstance(result, Mapping) else None
        if isinstance(expirations, list) and expirations:
            first = expirations[0]
            if isinstance(first, Mapping):
                return first
    return {}


def pick_spot(data: Mapping[str, Any], *, symbol: str | None, fallback: Any = None) -> Mapping[str, Any]:
    """Pick a spot object from aggregate or direct command data."""

    if "price" in data:
        return data
    spot = data.get("spot", {})
    if isinstance(spot, Mapping):
        if symbol and isinstance(spot.get(symbol), Mapping):
            return spot[symbol]
        direct = next((value for value in spot.values() if isinstance(value, Mapping)), None)
        if direct is not None:
            return direct
    return {"price": fallback}


def pick_series(data: Mapping[str, Any], key: str, symbol: str) -> list[Mapping[str, Any]]:
    """Pick a symbol-keyed series from aggregate data."""

    value = data.get(key, {})
    if isinstance(value, list):
        return [row for row in value if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        rows = value.get(symbol) or next((item for item in value.values() if isinstance(item, list)), [])
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)]
    return []


def pick_gex_history(data: Mapping[str, Any], symbol: str) -> list[Mapping[str, Any]]:
    """Pick GEX history snapshots and normalize them for sparklines."""

    history = data.get("gexHistory", {})
    if isinstance(history, Mapping):
        value = history.get(symbol) or next((item for item in history.values() if isinstance(item, Mapping)), {})
        snapshots = value.get("snapshots") if isinstance(value, Mapping) else None
        if isinstance(snapshots, list):
            return [
                {"value": nested_number(row, "netGex", "totalGexDollars"), **row}
                for row in snapshots
                if isinstance(row, Mapping)
            ]
    return []


def pick_fundamentals(data: Mapping[str, Any], symbol: str) -> list[Mapping[str, Any]]:
    """Pick the richest available fundamentals rows for a symbol."""

    fundamentals = data.get("fundamentals", {})
    if not isinstance(fundamentals, Mapping):
        return []
    for endpoint in ("ratios", "income", "balance-sheet", "cash-flow", "news"):
        value = fundamentals.get(endpoint)
        if isinstance(value, Mapping):
            rows = value.get(symbol) or next((item for item in value.values() if isinstance(item, list)), [])
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, Mapping)]
    return []


def first_level(levels: Sequence[Level], kind: str) -> Level | None:
    """Return the first level of a requested kind."""

    return next((level for level in levels if level.kind == kind), None)


def first_columns(rows: Sequence[Mapping[str, Any]], *, preferred: Sequence[str], limit: int) -> list[str]:
    """Choose stable table columns from preferred names plus first-seen keys."""

    seen: set[str] = set()
    columns: list[str] = []
    for name in preferred:
        if any(name in row for row in rows):
            seen.add(name)
            columns.append(name)
    for row in rows:
        for name in row:
            if name not in seen:
                seen.add(name)
                columns.append(name)
            if len(columns) >= limit:
                return columns
    return columns


def base_css(theme: Theme) -> str:
    """Generate the full report stylesheet."""

    return f"""
:root {{
  --bg: {theme.background};
  --surface: {theme.surface};
  --surface-alt: {theme.surface_alt};
  --text: {theme.text};
  --muted: {theme.muted};
  --border: {theme.border};
  --positive: {theme.positive};
  --negative: {theme.negative};
  --warning: {theme.warning};
  --accent: {theme.accent};
  --accent-2: {theme.accent_2};
  --font-display: {theme.font_display};
  --font-body: {theme.font_body};
  --radius: {theme.radius};
  --shadow: {theme.shadow};
  color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background:
    radial-gradient(circle at 18% 10%, color-mix(in srgb, var(--accent) 20%, transparent), transparent 28rem),
    radial-gradient(circle at 78% 18%, color-mix(in srgb, var(--positive) 12%, transparent), transparent 26rem),
    linear-gradient(135deg, var(--bg), color-mix(in srgb, var(--bg) 86%, #000));
  color: var(--text);
  font: 500 17px/1.45 var(--font-body);
}}
.report-shell {{
  width: min(1480px, calc(100% - 32px));
  margin: 0 auto;
  padding: 32px 0 48px;
}}
.report-header, .hero-grid, .metric-strip, .market-grid {{
  display: grid;
  gap: 14px;
}}
.report-header {{ grid-template-columns: 1fr auto; align-items: end; margin-bottom: 18px; }}
.eyebrow, .subtitle, .generated span, .metric-card span, .panel-title span {{
  color: var(--muted);
  margin: 0;
}}
h1, h2, h3, p {{ margin-top: 0; }}
h1 {{
  margin-bottom: 6px;
  font: 800 clamp(2.4rem, 5vw, 5rem)/.9 var(--font-display);
  letter-spacing: .02em;
  text-transform: uppercase;
}}
h2 {{
  margin: 0;
  font: 800 1.2rem/1 var(--font-display);
  letter-spacing: .08em;
  text-transform: uppercase;
}}
h3 {{
  font: 800 1.55rem/1 var(--font-display);
  letter-spacing: .05em;
  text-transform: uppercase;
}}
.generated, .ticker-lockup, .price-tape, .control-pill, .metric-card, .panel {{
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--surface) 92%, white 3%), var(--surface));
  box-shadow: var(--shadow);
}}
.generated {{ padding: 12px 16px; text-align: right; }}
.generated strong {{ display: block; font-family: var(--font-display); }}
.hero-grid {{ grid-template-columns: 1.1fr 1.3fr .8fr .9fr; margin: 14px 0; }}
.ticker-lockup, .price-tape, .control-pill {{ min-height: 92px; padding: 18px 20px; }}
.ticker-symbol {{
  color: var(--accent-2);
  font: 900 3.2rem/.82 var(--font-display);
  text-shadow: 0 0 22px color-mix(in srgb, var(--accent-2), transparent 54%);
}}
.ticker-title, .price-note, .control-pill span {{
  display: block;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: .12em;
}}
.price-main {{ color: var(--text); font: 800 3rem/.95 var(--font-display); }}
.control-pill strong {{
  color: var(--accent);
  font: 800 1.6rem/1.1 var(--font-display);
  text-transform: uppercase;
}}
.control-pill.accent strong {{ color: var(--positive); }}
.metric-strip {{ grid-template-columns: repeat(5, minmax(0, 1fr)); margin-bottom: 14px; }}
.metric-card {{ padding: 18px; min-height: 120px; }}
.metric-card strong {{ display: block; margin-top: 8px; font: 800 2rem/1 var(--font-display); }}
.metric-card small, .metric-delta {{ display: block; margin-top: 6px; color: var(--muted); }}
.sentiment-positive strong, .sentiment-positive h3 {{ color: var(--positive); }}
.sentiment-negative strong, .sentiment-negative h3 {{ color: var(--negative); }}
.sentiment-warning strong, .sentiment-warning h3 {{ color: var(--warning); }}
.market-grid {{ grid-template-columns: repeat(12, minmax(0, 1fr)); align-items: stretch; }}
.panel {{ padding: 18px; overflow: hidden; }}
.panel-title {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }}
.highlight-panel {{ border-color: color-mix(in srgb, var(--warning), var(--border)); }}
.span-4 {{ grid-column: span 4; }}
.span-5 {{ grid-column: span 5; }}
.span-7 {{ grid-column: span 7; }}
.span-12 {{ grid-column: 1 / -1; }}
.bar-chart {{ display: grid; gap: 7px; }}
.bar-row {{
  display: grid;
  grid-template-columns: 78px 1fr 112px;
  gap: 10px;
  align-items: center;
  min-height: 27px;
}}
.bar-strike {{ color: var(--accent); font: 800 1rem var(--font-display); text-align: right; }}
.bar-track {{
  position: relative;
  height: 25px;
  overflow: hidden;
  border-radius: 3px;
  background: color-mix(in srgb, var(--surface-alt) 75%, black);
}}
.bar-track i {{
  display: block;
  height: 100%;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--accent) 35%, transparent), var(--accent));
}}
.sentiment-negative .bar-track i {{
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--negative) 28%, transparent), var(--negative));
}}
.bar-track b {{
  position: absolute;
  inset: 3px auto 3px 8px;
  padding: 0 7px;
  border-radius: 5px;
  color: #001107;
  font: 900 .85rem/19px var(--font-display);
  background: var(--positive);
}}
.bar-track .badge-pivot {{ background: var(--warning); color: #150e00; }}
.bar-value {{ text-align: right; font: 800 1rem var(--font-display); }}
.node-callout {{ position: relative; min-height: 260px; padding-right: 92px; }}
.node-callout h3 {{ color: var(--warning); font-size: 2rem; }}
.node-callout li {{ margin: 10px 0; color: var(--text); }}
.node-target {{
  position: absolute;
  right: 8px;
  top: 20px;
  width: 74px;
  height: 74px;
  border: 5px solid var(--warning);
  border-radius: 50%;
}}
.node-target::before, .node-target::after, .node-target span {{
  content: "";
  position: absolute;
  background: var(--warning);
}}
.node-target::before {{
  left: 50%;
  top: -18px;
  width: 4px;
  height: 110px;
  transform: translateX(-50%);
}}
.node-target::after {{
  top: 50%;
  left: -18px;
  width: 110px;
  height: 4px;
  transform: translateY(-50%);
}}
.node-target span {{
  inset: 17px;
  border: 4px solid var(--warning);
  border-radius: 50%;
  background: transparent;
}}
.table-wrap {{ overflow: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: .96rem; }}
th, td {{ padding: 9px 8px; border-bottom: 1px solid var(--border); text-align: left; }}
th {{
  color: var(--accent);
  font-family: var(--font-display);
  text-transform: uppercase;
  letter-spacing: .06em;
  cursor: pointer;
}}
.level-map {{ position: relative; min-height: 330px; margin: 8px 24px; }}
.level-axis {{
  position: absolute;
  inset: 10px auto 10px 34px;
  width: 5px;
  border-radius: 999px;
  background: linear-gradient(var(--accent), var(--warning), var(--negative));
}}
.level-node, .spot-marker {{ position: absolute; left: 0; transform: translateY(50%); white-space: nowrap; }}
.level-node i {{
  display: inline-block;
  width: 28px;
  height: 28px;
  margin-right: 12px;
  border-radius: 50%;
  vertical-align: middle;
  background: var(--muted);
  box-shadow: 0 0 20px currentColor;
}}
.level-resistance {{ color: var(--accent); }}
.level-support {{ color: var(--negative); }}
.level-pivot {{ color: var(--warning); }}
.level-resistance i {{ background: var(--accent); }}
.level-support i {{ background: var(--negative); }}
.level-pivot i {{ background: var(--warning); }}
.spot-marker {{ left: 80px; color: var(--accent-2); font: 800 .95rem var(--font-display); }}
.heat-grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 6px; }}
.heat-cell {{
  aspect-ratio: 1;
  border-radius: 6px;
  background: color-mix(in srgb, var(--accent) calc(var(--heat) * 100%), var(--surface-alt));
}}
.heat-cell.neg {{
  background: color-mix(in srgb, var(--negative) calc(var(--heat) * 100%), var(--surface-alt));
}}
.legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; color: var(--muted); font-size: .9rem; }}
.legend i {{
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 6px;
  border-radius: 999px;
  background: var(--accent);
}}
.legend span:nth-child(2) i {{ background: var(--negative); }}
.legend span:nth-child(3) i {{ background: var(--warning); }}
.scenario-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
.scenario-card {{
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) - 4px);
  background: var(--surface-alt);
}}
.scenario-card ul {{ margin-bottom: 0; padding-left: 20px; }}
.spark-panel strong {{
  display: block;
  margin-top: 8px;
  font: 800 1.8rem/1 var(--font-display);
  color: var(--accent-2);
}}
.sparkline {{ width: 100%; height: auto; overflow: visible; }}
.sparkline polyline {{
  fill: none;
  stroke: var(--accent-2);
  stroke-width: 5;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 0 12px color-mix(in srgb, var(--accent-2), transparent 60%));
}}
.empty-state {{
  min-height: 120px;
  display: grid;
  place-items: center;
  color: var(--muted);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
}}
@media (max-width: 980px) {{
  .report-header, .hero-grid, .metric-strip, .scenario-grid {{ grid-template-columns: 1fr; }}
  .span-4, .span-5, .span-7, .span-12 {{ grid-column: 1 / -1; }}
  .bar-row {{ grid-template-columns: 58px 1fr 88px; }}
}}
"""


def client_script() -> str:
    """Return tiny no-dependency browser helpers for table sorting."""

    return """
document.querySelectorAll('table[data-sortable="true"] th').forEach((th, index) => {
  th.addEventListener('click', () => {
    const table = th.closest('table');
    const body = table.querySelector('tbody');
    const rows = Array.from(body.querySelectorAll('tr'));
    const direction = th.dataset.direction === 'asc' ? -1 : 1;
    th.dataset.direction = direction === 1 ? 'asc' : 'desc';
    rows.sort((a, b) => {
      const left = a.children[index].textContent.trim();
      const right = b.children[index].textContent.trim();
      const leftNumber = Number(left.replace(/[$,%KM]/g, ''));
      const rightNumber = Number(right.replace(/[$,%KM]/g, ''));
      if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
        return (leftNumber - rightNumber) * direction;
      }
      return left.localeCompare(right) * direction;
    });
    rows.forEach((row) => body.appendChild(row));
  });
});
"""


def percent_tag(value: float) -> str:
    """Return a compact intensity tag for bar annotations."""

    if value == 0:
        return ""
    sign = "+" if value > 0 else "-"
    return f"{sign}{min(abs(value) / 1_000_000, 999):.0f}M"


def nested_number(data: Mapping[str, Any], parent: str, child: str) -> float:
    """Read a nested number with zero fallback."""

    value = data.get(parent, {})
    if isinstance(value, Mapping):
        return as_number(value.get(child, 0.0))
    return 0.0


def number_or_none(value: Any) -> float | None:
    """Return a finite float or `None`."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(number):
        return number
    return None


def as_number(value: Any) -> float:
    """Return a finite float with zero fallback."""

    return number_or_none(value) or 0.0


def format_number(value: Any, *, digits: int = 0) -> str:
    """Format numeric display values with compact fallbacks."""

    number = number_or_none(value)
    if number is None:
        return "n/a"
    if abs(number) >= BILLION:
        return f"{number / BILLION:.{digits}f}B"
    if abs(number) >= MILLION:
        return f"{number / MILLION:.{digits}f}M"
    if abs(number) >= TEN_THOUSAND:
        return f"{number / THOUSAND:.{digits}f}K"
    return f"{number:,.{digits}f}"


def format_money(value: Any) -> str:
    """Format dollar values in compact finance notation."""

    number = as_number(value)
    sign = "-" if number < 0 else ""
    absolute = abs(number)
    if absolute >= BILLION:
        return f"{sign}${absolute / BILLION:.2f}B"
    if absolute >= MILLION:
        return f"{sign}${absolute / MILLION:.2f}M"
    if absolute >= THOUSAND:
        return f"{sign}${absolute / THOUSAND:.1f}K"
    return f"{sign}${absolute:.0f}"


def format_cell(value: Any) -> str:
    """Format arbitrary table cells without losing readable nested values."""

    if isinstance(value, float):
        return format_number(value, digits=2)
    if isinstance(value, int):
        return format_number(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value[:4])
    if isinstance(value, Mapping):
        return json.dumps(value, separators=(",", ":"))[:120]
    if value is None:
        return ""
    return str(value)


def esc(value: Any) -> str:
    """Escape text for safe HTML insertion."""

    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    sys.exit(main())
