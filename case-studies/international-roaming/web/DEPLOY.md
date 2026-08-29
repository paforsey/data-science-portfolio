# Deploying The Scenario Explorer

## What you need

Exactly two files, and they must stay together in the same folder:

- `index.html`
- `data.json`

That's it — no build step, no server code, no dependencies to install. `dist/`
(or `scenario-explorer.zip`) in this folder holds just those two files, ready
to copy or unzip wherever you're hosting.

**One hard requirement: it must be served over HTTP(S), not opened as a local
file.** `index.html` fetches `data.json` at load time, and browsers block that
`fetch()` under the `file://` protocol (opening the file by double-clicking).
Every option below serves it over HTTP by default, so this isn't something you
need to configure — just don't try to open `index.html` directly from Finder/Explorer.

---

## Option A — GitHub Pages (free, and this is already a GitHub repo)

1. In the repo's GitHub settings, open **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Pick the branch (e.g. `main`) and set the folder to
   `/case-studies/international-roaming/web` — or, if GitHub Pages requires
   `/root` or `/docs` in your plan, instead push a copy of `dist/`'s two files
   to whatever path you point Pages at.
4. Save. GitHub gives you a URL like
   `https://<your-username>.github.io/<repo-name>/case-studies/international-roaming/web/`
   — that's it, live in a minute or two.
5. To update later: replace `data.json` (see "Regenerating the data" in
   `README.md`) and push — no rebuild step, GitHub Pages just serves the new file.

## Option B — Netlify (drag-and-drop, no account setup beyond signup)

1. Go to [app.netlify.com/drop](https://app.netlify.com/drop).
2. Drag the `dist/` folder (or unzip `scenario-explorer.zip` first) onto the page.
3. Netlify uploads both files and gives you a live URL immediately
   (`https://random-name.netlify.app`).
4. Optional: claim the site in a free Netlify account to get a custom
   subdomain and keep the deploy for future updates (drag a new `data.json` in
   the same way to update it).

## Option C — Vercel

1. `npm i -g vercel` (one-time, needs Node.js installed), then from inside
   this `web/` folder: `vercel --prod`.
2. Follow the prompts (first run asks you to log in/create an account).
   Vercel deploys the current folder as a static site and gives you a URL.

## Option D — Any existing web host / datafxlab (upload via FTP/SFTP or your host's file manager)

1. Connect to your host (FTP client, SFTP, cPanel file manager, etc.).
2. Create a folder for this tool, e.g. `/scenario-explorer/`.
3. Upload `index.html` and `data.json` into that folder — nothing else needed.
4. Visit `https://yourdomain.com/scenario-explorer/index.html` (or just
   `/scenario-explorer/` if your host serves `index.html` by default for a
   directory, which most do).

## Option E — Amazon S3 (static website hosting)

1. Create an S3 bucket, enable **Static website hosting** in its properties,
   and set `index.html` as the index document.
2. Upload `index.html` and `data.json` to the bucket root (or a subfolder,
   matching whatever path you want in the URL).
3. Make both objects public (bucket policy or ACL), or put a CloudFront
   distribution in front of the bucket if you want HTTPS/a custom domain.
4. Use the bucket's website endpoint (or your CloudFront/custom domain) URL.

---

## Updating the data later

The page never needs to change — only `data.json` does. After re-running the
case study's notebooks, regenerate it with `build_data.py` (see `README.md`),
then re-upload just that one file wherever you deployed. Everything else about
this deploy stays the same.
