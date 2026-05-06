# MHQ Report Workflow

Use this workflow when an agent needs to turn MHQ data into a polished static HTML report.

1. Dump data with `scripts/mhq_data.py`.
2. Generate a first-pass report with `scripts/mhq_report.py`.
3. Open the generated HTML in Chromium and inspect layout density, visual hierarchy, and responsive behavior.
4. Edit the HTML directly or write a short no-dependency Python glue script that imports helpers from `mhq_report.py`.
5. Keep the final report self-contained: inline CSS, inline SVG, no external fonts, no remote scripts, no build step.

Useful commands:

```powershell
python skills\mhq-reports\scripts\mhq_data.py -h
python skills\mhq-reports\scripts\mhq_data.py all -h
python skills\mhq-reports\scripts\mhq_report.py -h
python skills\mhq-reports\scripts\mhq_report.py --data tests\unit\scriptjson\files.json -o report.html --symbol SPY
```

Design loop:

- Start with the strongest user intent: daily market structure, trade plan, earnings/fundamentals snapshot, macro board, or options dashboard.
- Pick one visual language, then stay consistent with colors, corner radius, type scale, and panel spacing.
- Use one dense hero section, one primary chart, two to four supporting panels, and a takeaway strip.
- Prefer concise copy with finance-specific interpretation: control node, support/resistance, volatility regime, dealer behavior, liquidity magnet, chop zone.
- Avoid dumping every field. Summarize and let tables carry raw details only when they help audit the claim.

When data is missing:

- Keep the panel in place with an `empty-state` message instead of silently dropping it.
- Write cautious language: "not loaded", "no rows in dump", or "requires a narrower query".
- Do not infer unavailable option greeks or financial values from unrelated fields.
