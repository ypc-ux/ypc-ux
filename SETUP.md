# Setup

This is a GitHub **profile README** — a self-updating one. A scheduled Action
redraws the stat SVGs daily from the GitHub GraphQL API; nothing loads from a
third-party service. It's wired for the `ypx-ux` account.

## 1. Create the repo

A GitHub repo named **exactly** `ypx-ux` (i.e. `ypx-ux/ypx-ux`). That name is
what makes it render on your profile page.

## 2. Fill in README.md

Replace the ALL-CAPS placeholders: name, links, bio, stack, projects. The
project links already point at `github.com/ypx-ux/...` — just rename the repos.

## 3. Push

```bash
git add -A
git commit -m "profile readme"
git branch -M main
git remote add origin git@github.com:ypx-ux/ypx-ux.git
git push -u origin main
```

## 4. Generate the stats now (don't wait for the 05:17 UTC cron)

GitHub → repo → **Actions** → "refresh stats" → **Run workflow**.
It commits `stats.svg`, `streak.svg`, `langs.svg`, `year.svg` and the `hd-*.svg`
headings. Until it runs, those image links 404 (the `hd-*.svg` headings are
already committed, so those work immediately).

If the push didn't enable Actions, flip it on under Settings → Actions → General,
and set "Workflow permissions" to **Read and write**.

## 5. (optional) ASCII portrait

```bash
pip install pillow numpy opencv-python-headless rembg onnxruntime
python3 scripts/make_portrait.py photo.png --crop LEFT,TOP,RIGHT,BOTTOM
python3 scripts/embed_portrait_font.py
```

First run downloads a ~176 MB background-removal model. Read the docstring in
`scripts/make_portrait.py` for photo requirements (side light, tight crop).
Then uncomment the `<img src="./ascii.svg" ...>` line in README.md.
