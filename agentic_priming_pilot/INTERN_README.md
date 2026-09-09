# Agentic Priming Local Pilot — Intern Setup & Operations Guide

**Welcome!** This guide will get you up to speed on the Agentic Priming system and how to operate it.

## What is Agentic Priming?

**Goal**: Prove that a local 87-heuristic scoring algorithm predicts real sales call conversion rates.

**Method**: 
1. **Phase 1/2** (completed): Find shops, verify phone numbers, output a confident call list
2. **Phase 3** (your responsibility): Score each script variant → Call shops → Log outcomes → Compare score vs booking rate → Generate case study with Wilson 95% confidence intervals

**Why it matters**: If score predicts conversion, we can use it to optimize sales approaches across many markets.

## System Architecture (High-Level)

```
Phase 1/2: shops.csv (verified call list)
    ↓
Phase 3 Database (pilot.db)
    ├── script_versions (your scripts)
    ├── baselines (pre-call scores for each script)
    └── attempts (real call outcomes: booked, declined, no_answer, etc.)
    ↓
Deerflow Workflow (automated loop)
    ├── Generate scripts with Ollama (local LLM)
    ├── Register in database
    ├── Score baselines (manual or API)
    ├── Batch call shops
    ├── Log outcomes
    ├── Analyze patterns
    └── Regenerate if needed
    ↓
case-study.md (final report with Wilson CIs)
```

## Setup (15 minutes)

### 1. Install Dependencies
```bash
cd agentic_priming_pilot
pip install -r requirements.txt
```

This installs:
- `ollama` — local LLM client
- `requests`, `phonenumbers`, `python-dotenv`
- `beautifulsoup4`, `lxml` (Phase 1/2)
- `playwright` (for browser automation)

### 2. Start Ollama Daemon
```bash
ollama serve
```

This starts Ollama on `localhost:11434`. Leave it running.

In another terminal, download the Mistral model (used for script generation):
```bash
ollama pull mistral
```

### 3. Verify Setup
```bash
python -m phase3.cli list
```

Should output:
```
  id  name                     context    score
```

If you see that, you're ready!

## Running the Workflow

### Option A: Deerflow UI (Recommended)
```bash
deerflow dashboard deerflow_workflow.yaml
```

Opens a web UI where you can:
- Click "Run Workflow" to start
- Watch progress in real time
- See logs for each step
- Pause/resume/stop as needed

### Option B: Manual CLI (If Deerflow unavailable)
```bash
# Step 1: Load shops
python -c "
from phase3.ollama_integration import load_shops_csv
shops = load_shops_csv('shops.csv')
print(f'Loaded {len(shops)} shops')
"

# Step 2: Generate scripts
python -c "
from phase3 import ollama_integration, store
conn = store.connect()
scripts = ollama_integration.generate_and_register_scripts(
    conn, context='auto body shop owner', num_variants=2
)
print(f'Generated {len(scripts)} scripts')
"

# Step 3: Score scripts (MANUAL — run this, then provide scores)
python -m phase3.cli list
# Then for each unscored script:
python -m phase3.cli score <id> --backend manual --total 72 --humanity pass

# Step 4: Call shops (simulated for MVP)
python -c "
from phase3 import call_executor, store
conn = store.connect()
shops = [...load from CSV...]
results = call_executor.batch_call_shops(shops, script_id=1, script_body='...', batch_size=10)
print(f'Called {len(results)} shops')
"

# Step 5: Log outcomes
python -c "
from phase3 import ollama_integration, store
conn = store.connect()
ollama_integration.log_outcomes_bulk(conn, results)
"

# Step 6: Generate report
python -m phase3.cli report

# Step 7: Generate case study (after ≥30 attempts)
python -m phase3.cli case-study --targets shops.csv --out case-study.md
"
```

## Monitoring Progress

### Real-time: Check Database
```bash
sqlite3 pilot.db

# List scripts
sqlite> SELECT id, name, context FROM script_versions;

# Check attempts so far
sqlite> SELECT COUNT(*) FROM attempts;
sqlite> SELECT outcome, COUNT(*) FROM attempts GROUP BY outcome;

# Booking rate
sqlite> SELECT 
  COUNT(CASE WHEN outcome='booked' THEN 1 END) * 1.0 / COUNT(*) as booking_rate
FROM attempts;
```

### Reports
```bash
# See quick summary
python -m phase3.cli report

# Generate full case study (needs ≥30 attempts)
python -m phase3.cli case-study --targets shops.csv --out case-study.md

# Read the case study
cat case-study.md
```

## Common Issues & Fixes

### "Ollama not responding"
```bash
# Check if daemon is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve
```

### "Script generation failed / Ollama unavailable"
- Workflow continues with fallback scripts
- Check daemon is running (see above)
- Try manually: `ollama pull mistral` to ensure model is cached

### "Manual scoring required"
- Workflow pauses at step 3
- Run: `python -m phase3.cli score <id> --backend manual --total <score> --humanity pass`
- Get scores from the real Agentic Priming scorer (external service)
- Resume workflow

### "Database locked"
- Another process is using pilot.db
- Check: `ps aux | grep python` or `ps aux | grep deerflow`
- Kill stray processes if needed
- Retry

### "Shops CSV not found"
- Phase 1/2 output should be `shops.csv` in this directory
- If missing, run Phase 1/2 pipeline: `python pipeline.py --zip 30035 --radius-miles 5 --out shops.csv`

### "Call execution failed"
- MVP uses simulated calls; should not fail
- If it does, check logs: `cat deerflow.log` or Deerflow UI logs
- Contact user for debugging

## What to Expect

### Iteration 1 (2 script variants, 10-20 calls)
- Workflow generates 2 initial scripts
- Scores them (requires manual input)
- Calls 10 shops (simulated calls)
- Logs outcomes
- Analyzes booking rate
- ~30 minutes total (plus manual scoring time)

### Iterations 2-5 (regenerate & call more)
- Workflow analyzes which script angle works better
- Regenerates 2 new variants with adaptations
- Scores new scripts
- Calls next 10 shops
- Continues until ≥50 attempts total
- ~2-3 hours for full cycle

### Final (Case Study)
- Once ≥30 attempts recorded, case study auto-generates
- Wilson 95% confidence intervals show booking rate range
- Compares against baseline script score
- Report shows whether score predicted conversion

## When to Contact User

- Ollama won't start or error persists after fixes
- Database corruption or "locked" errors
- Scoring backend unavailable (external API down)
- Workflow loops indefinitely or crashes
- Numbers look wrong (e.g., 0% booking rate after 20 calls)
- Unsure what to do next or Deerflow workflow stuck

**Do NOT**:
- Delete pilot.db or shops.csv
- Modify scripts after they've been scored (creates inconsistent data)
- Manually edit database (use CLI commands instead)

## Key Files You'll Interact With

| File | Purpose |
|------|---------|
| `deerflow_workflow.yaml` | Workflow definition; shows what happens in each step |
| `pilot.db` | SQLite database; inspect with `sqlite3 pilot.db` |
| `shops.csv` | Input from Phase 1/2; list of verified shops to call |
| `case-study.md` | Output; final report with conversion stats |
| `phase3/cli.py` | Command-line interface for manual operations |
| `phase3/ollama_integration.py` | High-level orchestration |
| `ollama_script_gen.py` | Ollama client; generates scripts |
| `phase3/call_executor.py` | Simulated call execution (MVP) |
| `deerflow.log` | Workflow execution logs |

## Environment Variables (`.env`)

```
# Phase 3: Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Phase 3: Deerflow
DEERFLOW_API_URL=http://localhost:8080
DEERFLOW_WORKFLOW_ID=agentic-priming-loop

# Phase 3: Scoring (when manual backend is ready)
AGENTIC_PRIMING_SCORER=manual
# AGENTIC_PRIMING_API_URL=
# AGENTIC_PRIMING_API_KEY=
```

## Troubleshooting Checklist

- [ ] Ollama daemon running (`curl http://localhost:11434/api/tags`)
- [ ] Python dependencies installed (`pip install -r requirements.txt`)
- [ ] pilot.db readable (`sqlite3 pilot.db "SELECT COUNT(*) FROM script_versions"`)
- [ ] shops.csv exists and has verified rows (`grep 'verified' shops.csv | wc -l`)
- [ ] Deerflow installed and running (`deerflow --version` and dashboard accessible)
- [ ] Workflow logs checked if something fails

## Next Steps

1. **Start the workflow**: `deerflow dashboard deerflow_workflow.yaml`
2. **Monitor progress**: Watch Deerflow UI or check database
3. **Provide scores**: When prompted, run `python -m phase3.cli score ...`
4. **Review results**: After ≥30 attempts, read `case-study.md`
5. **Contact user**: Report findings, ask for next steps

Good luck! You've got this.
