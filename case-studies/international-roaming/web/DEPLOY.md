# Deploying The Scenario Explorer

## What you need

Exactly two files, and they must stay together in the same folder:

- `index.html`
- `data.json`

That's it — no build step, no server code, no dependencies to install. Both
sit directly in this `web/` folder — or grab `scenario-explorer.zip`, which
holds just the two of them, ready to copy or unzip wherever you're hosting.

**One hard requirement: it must be served over HTTP(S), not opened as a local
file.** `index.html` fetches `data.json` at load time, and browsers block that
`fetch()` under the `file://` protocol (opening the file by double-clicking).
Every option below serves it over HTTP by default, so this isn't something you
need to configure — just don't try to open `index.html` directly from Finder/Explorer.

---

## Option A — Firebase Hosting

Firebase Hosting doesn't have a drag-and-drop upload in its console — deploys
go through the Firebase CLI, which needs [Node.js](https://nodejs.org) installed
first. Steps below assume you already have (or will create) a Firebase project.

1. **Install the CLI** (one-time): `npm install -g firebase-tools`
2. **Log in**: `firebase login` — opens a browser to authenticate with your
   Google account.
3. **Set up the project folder.** From inside this `web/` folder (or wherever
   you copied `index.html`/`data.json`):
   ```bash
   firebase init hosting
   ```
   - **"Please select an option"** → choose *Use an existing project* and pick
     your Firebase project (or *Create a new project* if you don't have one yet).
   - **"What do you want to use as your public directory?"** → point this at
     the folder that holds `index.html` and `data.json`. If you're running
     `init` from inside `web/` itself, answer `.`; if you copied those two
     files into a `public/` folder instead, answer `public`.
   - **"Configure as a single-page app (rewrite all urls to /index.html)?"** →
     `No` (there's only one page; no routing to rewrite).
   - **"Set up automatic builds and deploys with GitHub?"** → `No` (you're not
     using GitHub for this).
   - If it asks to overwrite an existing `index.html` in that folder, say
     `No` — you want to keep the one that's already there, not Firebase's
     placeholder page.
4. **Deploy**:
   ```bash
   firebase deploy --only hosting
   ```
5. The CLI prints your live URL, e.g. `https://<your-project-id>.web.app`.
6. **To update later** (e.g. after a data refresh): replace `data.json` in
   that same public directory and run `firebase deploy --only hosting` again
   — `index.html` never needs to change.

## Option B — Netlify (drag-and-drop, no account setup beyond signup)

1. Go to [app.netlify.com/drop](https://app.netlify.com/drop).
2. Unzip `scenario-explorer.zip` into an empty folder and drag that folder
   onto the page (keeps the upload to just the two files it needs).
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
