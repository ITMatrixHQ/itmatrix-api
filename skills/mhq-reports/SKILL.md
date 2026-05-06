---
name: mhq-reports
description: Build polished static HTML finance and trading reports from MHQ data. Use when users ask for market-structure dashboards, GEX/options visuals, static report sites, or HTML reports that should look excellent without external dependencies.
---
# MHQ Reports

Use this skill to create self-contained static HTML reports from MHQ v1 data. The skill is designed for LLM agents that can run no-dependency Python and produce browser-ready `.html` files. Ask the user what kind of report they want to build, if it's not very specific, query them for enough information about data, layout, and design to build something useful/appealing to them.

Use templates and examples proactively. Prioritize uncommon to moderately common template fusions, that are sensible and aesthetically appealing.

To not clutter the working directory, everything needs to go in a mhq-reports dir. You can add more sub-dirs there for data and reports. Build your report generators as pipelines so that they can easily be regenerated around updated json dumps.

Don't read `scripts/mhq_data.py` unless debugging is necessary. Instead explore what is available to you through the `-h`.

## Quick Start

1. Fetch data with `scripts/mhq_data.py`; inspect `scripts/mhq_data.py -h` and each subcommand's `-h` for exact coverage.
2. Generate a first-pass report with `scripts/mhq_report.py --data <dump.json> -o <report.html>`.
3. Improve the result by editing HTML directly or writing a small Python glue script that imports helpers from `scripts/mhq_report.py`.
4. Validate in Chromium when possible; static reports should work as a single local `.html` file.

## What Is Available

- `examples/demo.html`: An uncommon example of a bold static finance report layout.
- `scripts/mhq_data.py`: No-dependency MHQ `/api/v1` JSON dumper.
- `scripts/mhq_report.py`: No-dependency HTML generator and importable component toolkit.
- `templates/report-shell.html`: Plain HTML/CSS shell for hand-built reports.
- `templates/market-structure.html`: GEX ladder and level-map fragments.
- `templates/component-cards.html`: Metric and scenario card fragments.
- `templates/outlier-template-index.md`: Ranked palette, layout, and visualization ideas from familiar to rare.
- `templates/palette-catalog.css`: Copyable no-dependency CSS variable palettes.
- `templates/institutional-tear-sheet.html`, `exchange-floor-ledger.html`, `orbital-risk-map.html`, `spectral-liquidity-lab.html`: Full-page outlier layout templates.
- `templates/visual-fragments.html`: Ranked chart and shape fragments for custom reports.

## When To Use Each Resource

- Use `mhq_data.py` when the report needs fresh or specific v1 endpoint data.
- Use `mhq_report.py` when you need fast scaffolding, themes, default CSS, charts, legends, level maps, and safe HTML escaping.
- Use `templates/` when a bespoke report is easier to author by hand than through helper functions.
- Read `references/REPORT_WORKFLOW.md` for end-to-end workflow and data-fetching patterns.
- Read `references/COMPONENTS.md` for helper functions, layout classes, and chart/component options.
- Read `references/DESIGN_SYSTEM.md` for visual direction, theme selection, and finance-report design rules.

## Report Standards

Make reports self-contained: inline CSS, inline SVG, no external scripts, no package installs, no CDN dependencies. Prefer strong structure over decoration: hero, metrics, primary visual, supporting panels, scenario/takeaway strip. Use finance-native language only when the loaded data supports it.

When you are done, you must launch the html file in the browser for the user.
