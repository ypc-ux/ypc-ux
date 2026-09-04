# Setup

This is a GitHub **profile README** — a self-updating one. A scheduled Action
redraws the stat SVGs daily from the GitHub GraphQL API; nothing loads from a
third-party service.

## 1. Name the repo after your username

Create a GitHub repo named **exactly** your username (e.g. `jsmith/jsmith`).
That is what makes it render on your profile page.

## 2. Replace the placeholder

One string to swap everywhere — your GitHub login:

```bash
grep -rl YOUR_USERNAME . | xargs sed -i '' 's/YOUR_USERNAME/your-actual-login/g'
```

(The stats workflow itself reads `github.repository_owner`, so the SVGs will use
the right account regardless — this only fixes the `scripts/generate_stats.py`
local default and the README project links.)

## 3. Fill in README.md

Replace the ALL-CAPS placeholders: name, links, bio, stack, projects.

## 4. Push

```bash
git add -A
git commit -m "profile readme"
git branch -M main
git remote add origin git@github.com:your-actual-login/your-actual-login.git
git push -u origin main
```

## 5. Generate the stats now (don't wait for the 05:17 UTC cron)

GitHub → repo → **Actions** → "refresh stats" → **Run workflow**.
It commits `stats.svg`, `streak.svg`, `langs.svg`, `year.svg` and the `hd-*.svg`
headings. Until it runs, those image links 404 (the `hd-*.svg` headings are
already committed, so those work immediately).

If the push didn't enable Actions, flip it on under Settings → Actions → General,
and make sure "Workflow permissions" is set to **Read and write**.

## 6. (optional) ASCII portrait

```bash
pip install pillow numpy opencv-python-headless rembg onnxruntime
python3 scripts/make_portrait.py photo.png --crop LEFT,TOP,RIGHT,BOTTOM
python3 scripts/embed_portrait_font.py
```

First run downloads a ~176 MB background-removal model. Read the docstring in
`scripts/make_portrait.py` for photo requirements (side light, tight crop).
Then uncomment the `<img src="./ascii.svg" ...>` line in README.md.
