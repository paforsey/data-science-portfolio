# Deploying the International Roaming Price Scenario Tool

The tool is two files that must sit in the same folder: the page and
`data.json`, which the page fetches at load. They live in the datafxlab site
repo, not here:

```
paforsey/public/case-studies/international-roaming/scenario-analysis/
  scenario-analysis.html
  data.json
```

Published at
<https://paforsey.datafxlab.com/case-studies/international-roaming/scenario-analysis/scenario-analysis.html>.

This `web/` folder is where `data.json` is built (see `README.md`); the copy
beside the page is what the live site reads.

## Refreshing the data

1. Re-run the notebook, which refreshes `data/powerbi/`.
2. Regenerate the data from this case study's folder:
   ```bash
   cd case-studies/international-roaming
   python3 web/build_data.py
   ```
3. Copy it next to the page in the site repo:
   ```bash
   cp web/data.json \
     ../../../datafxlab/paforsey/public/case-studies/international-roaming/scenario-analysis/data.json
   ```
4. Deploy from the datafxlab repo:
   ```bash
   firebase deploy --only hosting:paforsey
   ```

The page itself never needs to change for a data refresh — only `data.json`
does, unless the data contract in `README.md` changes shape.

## Previewing locally

The page must be served over HTTP(S), not opened from disk: browsers block
`fetch()` of a local file under the `file://` protocol. From the site repo:

```bash
cd paforsey/public
python3 -m http.server 8000
# open http://localhost:8000/case-studies/international-roaming/scenario-analysis/scenario-analysis.html
```

## Hosting it somewhere else

The page and `data.json` are portable on their own, with no build step and no
server code. Copy both into any static host — a Netlify drop, a Vercel
project, an S3 bucket with static website hosting, or a plain web host over
FTP — keeping the two together in the same folder.
