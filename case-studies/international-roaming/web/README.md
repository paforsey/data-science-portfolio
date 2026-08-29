# The Scenario Explorer

A self-contained, static replacement for the Power BI handoff in `04_segmentation.ipynb`.
Reads the same aggregate tables the Power BI star schema uses — price sweep, macro
scenarios, segment revenue curves — and renders an interactive price/segment/economy
explorer with no BI login required.

## Files

| File | What it is |
|---|---|
| `dist/index.html` | The page. All markup, styles, and behavior; fetches `data.json` at load. This and `dist/data.json` are the only two files that exist — nothing is duplicated elsewhere. |
| `dist/data.json` | The only data the page reads. Small aggregates only (~7KB) — no account-level data. |
| `scenario-explorer.zip` | `dist/`'s two files, zipped, for easy drag-and-drop or handoff. |
| `build_data.py` | Regenerates `dist/data.json` from the notebook outputs. Run after re-running notebooks 01-04. |

## Deploying

`dist/` is the single, portable source of truth — it's fully self-contained
(no dependency on the rest of this repo). Copy `dist/`'s two files, or unzip
`scenario-explorer.zip`, to wherever you're hosting.

**See `DEPLOY.md` for step-by-step instructions** covering Firebase Hosting,
Netlify, Vercel, a plain web host via FTP, and S3.

`index.html` must be served over HTTP(S), not opened directly from disk — browsers
block `fetch()` of a local file under the `file://` protocol. To preview locally:

```bash
cd web/dist
python3 -m http.server 8000
# open http://localhost:8000/index.html
```

## Regenerating the data

After re-running notebooks 01-04 (which refreshes `data/synthetic/` and
`data/powerbi/`), regenerate `dist/data.json` from the project root:

```bash
cd case-studies/international-roaming
python3 web/build_data.py
```

Then re-zip if you're using `scenario-explorer.zip`:

```bash
cd web
zip -j scenario-explorer.zip dist/index.html dist/data.json
```

`dist/index.html` itself never needs to change for a data refresh — only
`dist/data.json` does.
