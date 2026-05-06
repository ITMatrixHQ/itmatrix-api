# Design System Notes

The skill includes three built-in themes in `scripts/mhq_report.py`.

`control-node`:

- Dark, neon, high-density trading terminal.
- Best for GEX, options, support/resistance, intraday playbooks, and control-node dashboards.
- Visual cues: electric blue resistance, green positive gamma, red negative gamma, yellow pivot/control level.

`paper-terminal`:

- Warm institutional note style.
- Best for fundamental summaries, morning notes, and print-friendly investment memos.
- Visual cues: cream surfaces, restrained borders, serif display typography, fewer glows.

`clear-macro`:

- Clean blue macro dashboard.
- Best for economy endpoints, treasury/inflation/labor reports, and multi-asset summaries.
- Visual cues: cool surfaces, broad spacing, lower contrast than the trading terminal.

The `templates/` directory also includes ranked outlier palettes and hand-authored templates. Use
`templates/outlier-template-index.md` as the chooser before loading individual template files.

Outlier template groups:

- `58% common` - `institutional-tear-sheet.html`: a credible editorial tear sheet that is familiar enough for stakeholders but less card-like than a dashboard.
- `34% common` - `exchange-floor-ledger.html`: a trading-floor notice board with tape strips, stamps, and loud hierarchy.
- `19% common` - `orbital-risk-map.html`: a radial/orbital map for reports where levels relate to each other like gravity wells.
- `7% common` - `spectral-liquidity-lab.html`: an ultraviolet lab-specimen report for rare, memorable, high-impact outputs.

Outlier palette families:

- `66% common` - `Sovereign Desk`: navy, ivory, oxblood, muted gold.
- `49% common` - `Circuit Pit`: graphite, electric cyan, safety orange, exchange green.
- `31% common` - `Miso Macro`: warm paper, black sesame, ume red, matcha green.
- `17% common` - `Polar Auction`: ice blue, seal black, aurora green, magenta stamp.
- `8% common` - `Ultraviolet Specimen`: ink black, ultraviolet, reagent yellow, arterial red.
- `3% common` - `Desert Exchange`: sand, iodine blue, cactus green, rust, bone.

Outlier visualization fragments:

- `62% common` - stratified bars for GEX, volume, or contribution ladders.
- `41% common` - tape river for price path or history through regimes.
- `23% common` - option constellation for connected strike and expiration nodes.
- `11% common` - liquidity fossil for static strike-core storytelling.

Visual standards:

- Use one dominant accent color, one positive color, one negative color, and one pivot/warning color.
- Keep chart labels visible without hover. Static reports should still read well in screenshots and PDFs.
- Use inline SVG for sparklines and shape diagrams; use CSS grid/divs for bar and heat charts.
- Put the strongest interpretation near the top right of the report, not below the fold.
- Prefer 12-column layouts on desktop and single-column stacking below 900px.
- If using an outlier template, commit fully to its metaphor. Do not mix institutional tear sheet, orbital map, and lab specimen motifs in one report.
- Avoid the default card-dashboard feel unless the user explicitly needs a familiar stakeholder dashboard.

Finance-specific visual patterns:

- Control-node panel: pivot number, short bullets, target/crosshair shape.
- GEX ladder: strike labels left, bars center, dollar values right.
- Level map: resistance above, pivot center, support below.
- Chop zone: two horizontal bounds with a zig-zag path between them.
- Scenario cards: bull, bear, chop with three bullets each.
- Audit tables: compact rows for fundamentals, requests, or underlying raw values.
