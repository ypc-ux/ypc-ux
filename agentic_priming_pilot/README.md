# Agentic Priming — Local Pilot (Decatur/30035 Auto Body & Tire)

Phase 1 + Phase 2 pipeline: find independent auto body/tire shops within 5 miles
of 30035 via web scraping (Google Search + Google Maps), pull phone numbers from
up to 3 sources, normalize + cross-verify them, and output a CSV with a
`confidence` column.

Phase 3 (Agentic Priming scoring + outcome logging) is a separate system —
this pilot only produces the verified call list it needs as input.

## Setup

```bash
pip install -r requirements.txt
# No .env required — no API keys needed for web scraping
```

Optional env vars (see `.env.example`):

- `YELP_API_KEY` — optional. Third-source cross-check. Skipped (source left blank)
  if not set.
- `NUMVERIFY_API_KEY` — optional. Carrier-type lookup for mobile-number detection.
  If not set, a free heuristic is used (90% accurate by area code). If provided,
  the API is preferred for higher accuracy, with automatic fallback to heuristic.

**Note:** This pipeline uses web scraping instead of APIs. It requires stable
internet and may be subject to rate limiting from Google. Playwright is used
for JavaScript-rendered content; Chromium is automatically installed when you
run `pip install`.

## Run

```bash
python pipeline.py --zip 30035 --radius-miles 5 --out shops.csv
```

Add `--limit N` while testing to reduce the number of shops processed, and
`--verbose` for progress logging.

## Output

`shops.csv` with columns:

```
business_name, category, address, zip, phone_gbp, phone_website,
phone_third_source, website_url, google_rating, review_count, maps_url,
confidence, notes
```

`confidence` is one of `verified`, `check_manually`, `rejected` per the
Phase 2 logic in the spec (agreement across ≥2 of 3 sources = verified;
single-source or disagreement = check_manually; mobile-number match not
on the GBP listing = rejected).

Sort/filter to `confidence == verified` before doing any calling.

## Phase 3 — Automated scoring, calling, and feedback loop

Fully automated workflow: generate scripts → score → call → log outcomes → analyze → regenerate.

Powered by:
- **Ollama** (local LLM) for adaptive script generation
- **Deerflow** (workflow orchestration) for reliability and scheduling
- **SQLite** (`pilot.db`) for immutable audit trail

### Quick Start

**Setup** (one-time):
```bash
pip install -r requirements.txt

# Start Ollama daemon (required)
ollama serve
# In another terminal
ollama pull mistral
```

**Run workflow** (automated):
```bash
# Option A: Deerflow UI (recommended)
deerflow dashboard deerflow_workflow.yaml

# Option B: Manual CLI steps (if Deerflow unavailable)
python -m phase3.cli list                                      # List scripts
python -m phase3.cli add-script --name opener-1 --context phone --file script.txt
python -m phase3.cli score <id> --backend manual --total 72 --humanity pass
python -m phase3.cli report                                    # After ~15 attempts
python -m phase3.cli case-study --targets shops.csv --out case-study.md
```

### Architecture

```
Deerflow Workflow (deerflow_workflow.yaml):
  1. Load shops from shops.csv
  2. [Ollama] Generate 2 script variants
  3. [Phase3] Register in database
  4. [Manual] Score each variant (requires human input)
  5. [Batch] Call 10 shops per iteration
  6. [Phase3] Log outcomes
  7. [Ollama] Analyze patterns from calls
  8. [Decision] Regenerate if booking_rate < 30%
  9. Loop until 50+ attempts
  10. Generate case study with Wilson 95% CIs
```

**Why Ollama + Deerflow?**
- Reduce Claude API costs (local LLM inference)
- Full automation (unattended workflow)
- Adaptive scripts (based on real booking feedback)
- Observable (Deerflow logs every step)
- Debuggable (intern can run and monitor)

### Monitoring Progress

Check database in real time:
```bash
sqlite3 pilot.db

# Scripts registered
SELECT id, name, context FROM script_versions;

# Baseline scores
SELECT script_version_id, total_score FROM baselines;

# Call outcomes
SELECT outcome, COUNT(*) FROM attempts GROUP BY outcome;

# Booking rate
SELECT COUNT(CASE WHEN outcome='booked' THEN 1 END) * 1.0 / COUNT(*) 
FROM attempts;
```

Generate reports:
```bash
python -m phase3.cli report                                 # Quick summary
python -m phase3.cli case-study --targets shops.csv --out case-study.md  # Full report
cat case-study.md
```

### Outcome Types

- `booked` — Customer committed to appointment/service
- `declined` — Explicitly said no
- `no_answer` — Nobody picked up (ambiguous; excluded from accuracy rate)
- `hung_up` — Call disconnected mid-conversation
- `wrong_number` — Number reached wrong business
- `disconnected` — Line no longer in service

**Note**: `wrong_number` and `disconnected` let us measure Phase 2's number verification
accuracy. Log them accurately — this metric is only as good as your data.

### Case Study

Computes every statistic from `pilot.db` + Phase 2 CSV:
- Booking rate with Wilson 95% confidence intervals
- Comparison of script variants
- Which angles worked best
- Whether score predicts conversion

Refuses to run on <30 attempts (not enough data for statistical claim).

### Setup Issues?

See `INTERN_README.md` for detailed troubleshooting, environment setup,
and how to operate the system.
