# The Scenario Explorer

A self-contained, static replacement for the Power BI handoff in `04_segmentation.ipynb`.
Reads the same aggregate tables the Power BI star schema uses — price sweep, macro
scenarios, segment revenue curves — and renders an interactive price/segment/economy
explorer with no BI login required.

## Files

| File | What it is |
|---|---|
| `index.html` | The page. All markup, styles, and behavior; fetches `data.json` at load. |
| `data.json` | The only data the page reads. Small aggregates only (~7KB) — no account-level data. |
| `build_data.py` | Regenerates `data.json` from the notebook outputs. Run after re-running notebooks 01-04. |

## Deploying

Both `index.html` and `data.json` must be served together from the same folder —
copy this whole `web/` directory to wherever it's hosted (static hosting only,
no server-side code needed: GitHub Pages, Netlify, S3, or any static file host).

`index.html` must be served over HTTP(S), not opened directly from disk — browsers
block `fetch()` of a local file under the `file://` protocol. To preview locally:

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000/index.html
```

## Regenerating the data

After re-running notebooks 01-04 (which refreshes `data/synthetic/` and
`data/powerbi/`), regenerate `data.json` from the project root:

```bash
cd case-studies/international-roaming
python3 web/build_data.py
```

`index.html` itself never needs to change for a data refresh — only `data.json` does.
