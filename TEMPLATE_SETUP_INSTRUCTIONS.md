# GitHub Template Repo Setup Instructions

The Agentic Priming template has been created locally at `/tmp/agentic-priming-template`.

This template is ready to be pushed to GitHub as a separate **template repository** that others (like your friend) can use via the "Use this template" button.

---

## Step 1: Create Empty Repo on GitHub

Go to https://github.com/ypc-ux (or your organization) and create a new repository:

- **Name**: `agentic-priming-template`
- **Description**: "Automated local sales/outreach pilot using Ollama, Deerflow, and web scraping. No API keys required."
- **Visibility**: Public (so others can see it)
- **Initialize**: Leave empty (don't add README, .gitignore, or license)
- **Template repository**: ✅ Check this box!

Click **Create repository**.

---

## Step 2: Push Template to GitHub

```bash
cd /tmp/agentic-priming-template

# Add GitHub origin
git remote add origin https://github.com/ypc-ux/agentic-priming-template.git

# Push to main
git branch -M main
git push -u origin main
```

---

## Step 3: Verify Template Repo

Visit: https://github.com/ypc-ux/agentic-priming-template

You should see:
- ✅ All files present (README, YOUR_OPERATION, scripts, etc.)
- ✅ "Use this template" button visible (green button at top-right)
- ✅ Template indicator saying "This is a template repository"

---

## Step 4: Share With Your Friend

Send your friend this link:
```
https://github.com/ypc-ux/agentic-priming-template
```

They click "Use this template" and get their own copy with all the customization guides built-in.

---

## Step 5: Next Steps for Template Improvements

As you find issues or improvements, update the template:

```bash
cd /tmp/agentic-priming-template

# Make changes
echo "# New content" >> README.md

# Commit and push
git add README.md
git commit -m "docs: Update README with new section"
git push origin main
```

---

## Template Contents Summary

```
agentic-priming-template/
├── README.md                    # Main guide (5 min quick start)
├── YOUR_OPERATION.md            # Customization guide (8 sections)
├── QUICK_REFERENCE.md           # Commands & troubleshooting
├── CONTRIBUTING.md              # How to contribute back
├── LICENSE                      # MIT
├── .env.example                 # Environment variables
├── .gitignore                   # Git ignore patterns
├── requirements.txt             # Python dependencies
└── scripts/
    ├── setup.sh                 # One-time setup (venv, deps, Ollama)
    └── run_pilot.sh             # Interactive pilot runner
```

**Key features**:
- ✅ No API keys required (uses Ollama + heuristics)
- ✅ One-command setup: `bash scripts/setup.sh`
- ✅ Interactive setup: `bash scripts/run_pilot.sh`
- ✅ Fully customizable: `YOUR_OPERATION.md` (8 sections)
- ✅ Well-documented: README, quick reference, contributing guide

---

## What Users Can Do With This

### Your Friend
```bash
git clone <their fork> agentic-priming-friend
cd agentic-priming-friend
bash scripts/setup.sh
bash scripts/run_pilot.sh
# Runs full campaign for their business
```

### Public Users (Future)
- Fork from GitHub template button
- Customize for their industry
- Run automated campaigns
- Share results

### Contributions
- Industry templates (pest control, HVAC, etc.)
- Script angle libraries
- Objection response databases
- Performance benchmarks

---

## Future Template Enhancements

### Phase 1 (This Sprint) - Done ✅
- [x] Basic README + getting-started
- [x] Customization guide (YOUR_OPERATION.md)
- [x] Setup scripts (automated)
- [x] Quick reference guide
- [x] MIT License

### Phase 2 (Next Sprint) - Recommended
- [ ] Cookiecutter template (one-liner setup)
- [ ] Docker image (docker run)
- [ ] GitHub Actions CI (auto-test on PR)
- [ ] Industry templates subdirectory

### Phase 3 (Q1 2025) - Nice-to-Have
- [ ] GitHub Marketplace action
- [ ] Demo videos
- [ ] Community contributions
- [ ] Benchmark leaderboard

---

## How to Update Template from Main Repo

If you make improvements to the main codebase (in `/home/user/ypc-ux`), sync them to template:

```bash
# In template repo
cd /tmp/agentic-priming-template

# Copy updated files from main repo
cp /home/user/ypc-ux/agentic_priming_pilot/pipeline.py ./agentic_priming_pilot/
cp /home/user/ypc-ux/agentic_priming_pilot/phase3/*.py ./agentic_priming_pilot/phase3/

# Commit and push
git add -A
git commit -m "sync: Update from main repo"
git push origin main
```

This keeps the template in sync with your production codebase.

---

## Done! 🎉

Your template repo is ready. Users can now:
1. Go to https://github.com/ypc-ux/agentic-priming-template
2. Click "Use this template"
3. Get their own copy with all instructions built-in
4. Customize for their business (8-section guide included)
5. Run full campaign with 1 command

**Share with your friend now!**
