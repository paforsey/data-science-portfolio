# International Roaming Price Scenario Tool

A self-contained, static decision-support tool for the international roaming
pricing case study. Given a candidate roaming-pass price, it shows the
expected annual revenue benefit alongside the expected purchaser cost, under
three economic conditions, with the simulation's uncertainty shown alongside
each estimate — no BI login required.

Revenue is fully wired up. Purchaser figures are available at the **segment**
grain (a deterministic expected-value decomposition — see the notebook's
"Build Segment Purchaser Curves" section) but **not yet** at the portfolio or
economic-scenario grain, where a properly simulated figure with a p5–p95
interval is needed (see "Adding portfolio-level purchaser data" below). The
tool discloses this asymmetry explicitly rather than approximating the
missing piece, and stays fully usable for revenue exploration in the meantime.

## Files

| File | What it is |
|---|---|
| `index.html` | The page. All markup, styles, and behavior; fetches `data.json` at load. |
| `data.json` | The only data the page reads. Small aggregates only (~5KB) — no account-level data. |
| `scenario-explorer.zip` | `index.html` + `data.json`, zipped, for easy drag-and-drop or handoff. |
| `build_data.py` | Regenerates `data.json` from the Power BI export tables. Run after re-running the notebook. |

Only `index.html` and `data.json` are actually needed to run the page — the
other files here are for maintaining/deploying it, not part of the page itself.

## Deploying

`index.html` and `data.json` are fully portable on their own (no dependency
on the rest of this repo). Copy both, or unzip `scenario-explorer.zip`, to
wherever you're hosting.

**See `DEPLOY.md` for step-by-step instructions** covering Firebase Hosting,
Netlify, Vercel, a plain web host via FTP, and S3.

`index.html` must be served over HTTP(S), not opened directly from disk — browsers
block `fetch()` of a local file under the `file://` protocol. To preview locally:

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000/index.html
```

## Regenerating the data

After re-running the notebook (which refreshes `data/powerbi/`), regenerate
`data.json` from the project root:

```bash
cd case-studies/international-roaming
python3 web/build_data.py
```

`build_data.py` validates the export as it reads it (grid consistency,
`p5 <= median <= p95`, non-negative revenue, a shared `run_id`, and a
consistency check between the two independent "Base" simulation runs) and
fails loudly rather than writing a `data.json` built on a broken assumption.

Then re-zip if you're using `scenario-explorer.zip`:

```bash
cd web
zip -j scenario-explorer.zip index.html data.json
```

`index.html` itself never needs to change for a data refresh — only
`data.json` does, unless the data contract below changes shape.

## Data contract

`data.json` currently carries:

- `meta` — run id, current/recommended price, behavioral-case scale factors,
  the segment/portfolio reconciliation gap, `purchasers_available: false`
  (portfolio/scenario grain), and `segment_purchasers_available: true`.
- `grid` — the full 13-point evaluated price grid (0.90x–1.20x).
- `portfolio` — revenue p5/median/p95 across the full grid, for the "as
  fitted" and "joint sensitivity" cases, unconditioned on macro scenario
  (what the tool calls the Base economy). No purchaser fields yet.
- `scenarios.expansion` / `scenarios.contraction` — revenue p5/median/p95 at
  exactly the three prices the macro simulation was run at (1.00x,
  recommended, 1.20x), always under the joint-sensitivity case. No purchaser
  fields yet.
- `segOrder` / `segMeta` / `segCurve` — the four pricing-eligible segments'
  revenue **and expected purchasers** across the full grid, both deterministic
  expected-value decompositions (not simulated — no interval). Purchasers is
  the per-account `1 − ∏(p_null over that account's forward trips)`, summed
  within segment; see the notebook's "Build Segment Purchaser Curves" cell
  and the tool's own Methodology section for the independence assumption.
- `dormant` — the excluded Dormant segment's size, for disclosure only.

### Adding portfolio-level purchaser data

The segment-grain purchaser figures above (Track A) reuse data and code that
already existed for segment revenue — no new simulation. Portfolio and
economic-scenario purchasers (Track B) are a different, larger piece of work:
they need a genuinely *simulated* figure with a p5–p95 interval, paired
against revenue from the same Monte Carlo draws — not a second, independent
simulation, which would break the pairing needed for a valid interval or a
`revenue_per_purchaser_lost` figure.

Concretely: the notebook's `simulate()` function currently only accumulates
`simulated_revenue[iteration]`. It would need a second per-iteration
accumulator — e.g. track which accounts had at least one non-null-coverage
trip that iteration, count them — output alongside revenue from every call.
`simulate()` is invoked for the full 13-point sweep (both cases) and the
3-scenario × 3-price macro runs; both call sites, and the tables they feed
(`fact_portfolio_simulation`, `fact_macro_scenario`), would need the new
`purchasers_median`/`_p5`/`_p95` columns.

Once those exist, `data.json` needs, mirroring the revenue fields:

- `portfolio.<case>.purchasers_median` / `_p5` / `_p95`, full grid, both cases.
- `scenarios.<scenario>.purchasers_median` / `_p5` / `_p95`, at the three
  macro-simulation prices.

— at which point `meta.purchasers_available` flips to `true` and the page's
purchaser chart, decision-summary cost column, and `revenue_per_purchaser_lost`
figure can be lit up. Until then, don't fabricate or approximate them here.
