# International Roaming Price Scenario Tool

A self-contained, static decision-support tool for the international roaming
pricing case study. Given a candidate roaming-pass price, it shows the
expected annual revenue benefit alongside the expected purchaser cost, under
three economic conditions, with the simulation's uncertainty shown alongside
each estimate — no BI login required.

Revenue is fully wired up. Purchaser figures are **not currently available**
(see "Adding purchaser data" below) — the tool discloses this explicitly
rather than approximating them, and stays fully usable for revenue
exploration in the meantime.

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
  the segment/portfolio reconciliation gap, and `purchasers_available: false`.
- `grid` — the full 13-point evaluated price grid (0.90x–1.20x).
- `portfolio` — revenue p5/median/p95 across the full grid, for the "as
  fitted" and "joint sensitivity" cases, unconditioned on macro scenario
  (what the tool calls the Base economy).
- `scenarios.expansion` / `scenarios.contraction` — revenue p5/median/p95 at
  exactly the three prices the macro simulation was run at (1.00x,
  recommended, 1.20x), always under the joint-sensitivity case.
- `segOrder` / `segMeta` / `segCurve` — the four pricing-eligible segments'
  revenue across the full grid (a deterministic expected-value decomposition,
  not simulated — no interval).
- `dormant` — the excluded Dormant segment's size, for disclosure only.

### Adding purchaser data

No parquet export currently carries a purchaser figure at any grain, so the
tool shows an explicit "not available" state for the whole cost side of the
revenue/purchaser trade-off rather than deriving or approximating one.

To light that up, `data.json` would need, mirroring the revenue fields above:

- `portfolio.<case>.purchasers_median` / `_p5` / `_p95`, full grid, both cases.
- `scenarios.<scenario>.purchasers_median` / `_p5` / `_p95`, at the three
  macro-simulation prices.
- `segCurve.<id>.purchasers` (and, if ever simulated per segment, `_p5`/`_p95`).

The natural source is `data/synthetic/account_price_response.parquet`
(per-account `p_null` at four prices) rolled up via
`1 - product(p_null over an account's forward trips)`, per account, then
summed — see the case study notebook's purchaser-definition note — but that
table only covers four prices and no macro scenario, and rolling it up is
notebook-level work, not a `build_data.py` change. Until the notebook exports
it at the full grid/scenario/case grain, don't fabricate it here.
