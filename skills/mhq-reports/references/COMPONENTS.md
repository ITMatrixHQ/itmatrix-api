# Component Reference

`scripts/mhq_report.py` is both a CLI and an importable helper module. Import it from a one-off script when the generated report needs custom layout:

```python
from pathlib import Path
from skills.mhq_reports.scripts import mhq_report  # If packaged/import path is adjusted.
```

In ad hoc repo scripts, direct file loading is often simpler:

```python
import importlib.util
from pathlib import Path

module_path = Path("skills/mhq-reports/scripts/mhq_report.py")
spec = importlib.util.spec_from_file_location("mhq_report", module_path)
mhq_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mhq_report)
```

Core helpers:

- `page(title, body, theme, eyebrow="", subtitle="")`: Full self-contained HTML shell.
- `panel(title, body, class_name="")`: Reusable report card with heading chrome.
- `metric_strip(metrics)`: Responsive metric cards from `Metric` objects.
- `gex_bar_chart(rows)`: Horizontal positive/negative gamma bars.
- `heat_grid(rows, cells=48)`: Compact heat cells for strike or matrix intensity.
- `level_map(levels, spot_price=...)`: Vertical support/pivot/resistance map.
- `sparkline(values)`: Inline SVG sparkline.
- `table(rows, columns)`: Sortable static table with escaped cells.
- `legend(labels)`: Compact legend row.

Data helpers:

- `pick_gex_result(data, symbol=None, expiration=None)`: Selects one GEX payload from aggregate or direct dumps.
- `pick_spot(data, symbol=None, fallback=None)`: Selects a spot payload.
- `gex_rows(gex)`: Flattens `gexByStrike` into `{"strike", "value", "tag"}` rows.
- `infer_levels(gex, spot_price=...)`: Derives pivot, support, and resistance levels.
- `pick_series(data, "stockBars", symbol)`: Selects bar rows for sparklines.
- `pick_fundamentals(data, symbol)`: Selects a fundamentals row set for audit tables.

Layout classes:

- `span-4`, `span-5`, `span-7`, `span-12`: Grid widths in the 12-column report grid.
- `sentiment-positive`, `sentiment-negative`, `sentiment-warning`: Color semantic content.
- `highlight-panel`: Warning-accent panel border for the main callout.
- `empty-state`: Missing-data placeholder.

Use direct HTML when it is faster:

- `templates/report-shell.html`: Base shell for hand-authored reports.
- `templates/market-structure.html`: GEX bar and level-map fragments.
- `templates/component-cards.html`: Metric and scenario card fragments.
- `templates/outlier-template-index.md`: Ranked guide for choosing familiar, uncommon, rare, and extremely rare visual directions.
- `templates/palette-catalog.css`: CSS variable palettes that can be copied into any self-contained report.
- `templates/institutional-tear-sheet.html`: Familiar editorial desk-note layout with stronger typography and table rhythm.
- `templates/exchange-floor-ledger.html`: Exchange-floor notice board with tape strips and stamped hierarchy.
- `templates/orbital-risk-map.html`: Radial structure map for levels, expirations, and scenario gravity.
- `templates/spectral-liquidity-lab.html`: Rare lab/specimen style for high-impact market-structure reports.
- `templates/visual-fragments.html`: Copyable visualization fragments including stratified bars, tape river, constellation, and liquidity fossil.
