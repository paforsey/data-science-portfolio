# International Roaming Price Scenario Tool

A self-contained, static decision-support tool for the international roaming
pricing case study. Given a candidate roaming-pass price, it shows the
expected annual revenue benefit alongside the expected purchaser cost, under
three economic conditions, with the simulation's uncertainty shown alongside
each estimate — no BI login required.

Both sides of the trade-off are wired up: revenue and purchasers, at the
portfolio, economic-scenario, and segment grain. Portfolio and
economic-scenario purchasers are genuinely *simulated* — counted inside the
same Monte Carlo loop as revenue, from the same draws, so the two stay
properly paired — while segment purchasers remain the deterministic
expected-value figure Track A added (no interval; see the notebook's "Build
Segment Purchaser Curves" section). The tool discloses this methodological
difference rather than blurring it.

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

`build_data.py` validates the export as it reads it — grid consistency,
`p5 <= median <= p95` for revenue and purchasers, non-negative values,
purchasers never exceeding `eligible_accounts`, a shared `run_id`, and a
consistency check between the two independent "Base" simulation runs — and
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

- `meta` — run id, current/recommended price, the sensitivity ceilings
  (`response_scale_joint_sensitivity`/`depth_scale_joint_sensitivity` — now
  slider endpoints, not a bundled case label), the segment/portfolio
  reconciliation gap, `purchasers_available: true`,
  `segment_purchasers_available: true`, and `eligible_accounts` — the
  forward-panel population (`N_ACCOUNTS_PANEL` in the notebook) that every
  purchaser figure on the page is drawn from and rated against.
- `grid` — the full 13-point evaluated price grid (0.90x–1.20x).
- `sensitivityGrid` — the Base-economy revenue/purchaser surface, indexed by
  **two independent controls** (`responseScale`, `depthScale`; 3 points each,
  1.00x to a diagnostic-derived ceiling) instead of one bundled "behavioral
  case." `cells["<ri>_<di>"]` holds the same `revenue_*`/`purchasers_*`
  p5/median/p95 shape as everything else, for every point on the 3x3 grid at
  the full 13-point price grid. Replaces the old `portfolio` field (see
  "From bundled case to two sliders" below) as what the tool actually reads
  for Base; `portfolio`/`dim_model_case` still exist in the parquet layer
  but nothing in the UI consumes them any more.
- `scenarios.expansion` / `scenarios.contraction` — revenue and purchasers
  p5/median/p95 at exactly the three prices the macro simulation was run at
  (1.00x, recommended, 1.20x), always at both sliders' ceiling — that
  combination is the only point the macro simulation covers. Each also
  carries `paired_at_recommended`: a genuinely paired revenue/purchaser
  difference (1.15x vs. 1.00x, same iterations) — the tool prefers this over
  subtracting two marginal medians whenever the scenario and selected price
  make it valid, per the spec's preference for paired simulation differences.
- `segOrder` / `segMeta` / `segCurve` — the four pricing-eligible segments'
  revenue **and expected purchasers** across the full grid, both deterministic
  expected-value decompositions (not simulated — no interval, unlike the
  simulated portfolio/scenario figures above), fixed at both sliders'
  ceiling. Purchasers is the per-account
  `1 − ∏(p_null over that account's forward trips)`, summed within segment;
  see the notebook's "Build Segment Purchaser Curves" cell and the tool's own
  Methodology section for the independence assumption.
- `dormant` — the excluded Dormant segment's size, for disclosure only.
- `probCurve` — population-mean P(null)/P(partial)/P(full) across the full
  grid, indexed `"0"`/`"1"`/`"2"` matching `sensitivityGrid.responseScale`.
  This is the State Model's fitted price-response mechanism itself (not
  simulated, not a distribution — a direct mean of
  `probs_at(price, response_scale)` over the forward panel), **not**
  conditioned on economic scenario (macro shift only ever affects trip
  occurrence) or on `depthScale` (which only touches revenue magnitude, never
  coverage-state probability — see the depth-invariance check `build_data.py`
  doesn't enforce but the notebook's sensitivity grid empirically satisfies).
  Not currently rendered — the page's "Simulation inputs and their
  distributions" visual that read this was removed; the field stays in
  the export (like `portfolio`/`dim_model_case`) in case it's wanted again.

### From bundled case to two sliders

The tool originally toggled "As fitted" vs. "Joint stronger-response
sensitivity" as one switch — but those two numbers (response_scale ≈1.76×,
depth_scale ≈1.04×) come from unrelated models and unrelated diagnostics (a
regional holdout on the State Model; a label-contamination check on the
Magnitude Model) and were only ever bundled by convention, not by any
statistical link between them. They're now two independent sliders. The
underlying scorers (`score_trips`, the Magnitude Model's revenue function)
were already continuous in these parameters — the notebook's State Model
("Export Results") and Magnitude Model ("Export Magnitude-Model Results")
sections now each export 3 scenario points (`'base'/'mid'/'stronger'` and
`'reported'/'mid'/'stronger'`) instead of 2, and `probs_at()`/`rev_at()` in
"Configure Simulation" do nearest-grid-point matching across those 3 points
instead of a binary check — so this reaches further upstream than the
purchaser work did, but didn't require re-deriving anything that wasn't
already there. A coarser 3-point grid was chosen deliberately over a finer
one to start; revisit `RESPONSE_SCALE_GRID`/`DEPTH_SCALE_GRID` in "Configure
Simulation" if more resolution is wanted later.

Deliberately **not** done: crossing this grid with Economic Scenario.
Expansion/Contraction stay fixed at both ceilings, exactly as before — a
full 3 (economy) x 3 (response) x 3 (depth) simulation matrix wasn't worth
building for a control combination nobody asked for. See "Sweep Sensitivity
Grid" in the notebook for the reasoning.

### How purchasers are simulated (Track B)

The notebook's `simulate()` function accumulates `simulated_revenue[iteration]`
inside its Monte Carlo loop; it now optionally also accumulates
`simulated_purchasers[iteration]` from the *same* per-iteration draws — an
account counts as a purchaser that iteration if any of its forward trips
occurred and landed in a non-null coverage state. This is gated behind a
`track_purchasers=False` keyword so every diagnostic-only call site
(convergence checks, the antithetic-variance comparison, the baseline
distribution) is unchanged; only the full price sweep and the macro-scenario
cell pass `track_purchasers=True` and export the result.

Implementation: `ACCOUNT_IDX = pd.factorize(panel['account_id'])[0]` maps
each forward-trip row to an integer account index once, up front; per
iteration, `np.bincount(ACCOUNT_IDX, weights=purchased_trip, minlength=N_ACCOUNTS_PANEL) > 0`
gives a per-account purchased-this-iteration flag in one vectorized call, and
`.sum()` is the iteration's purchaser count. Segment-level purchasers were
deliberately **not** extended to simulated intervals — the deterministic
Track A figure stays as documented above; see the commit history for why.
