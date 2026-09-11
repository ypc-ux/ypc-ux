# Agentic Priming Pilot — Sales Outreach Engine Superagent

## What It Does
Automated sales outreach pipeline that finds prospects, generates personalized scripts, makes calls, tracks outcomes, and builds case studies from real data. The system gets smarter with every campaign.

Phase 3 (current) adds:
- Script variant management (multiple versions of the same script)
- Pre-call baseline scoring (score scripts before making calls)
- Outcome logging (booked, declined, no_answer, hung_up)
- Batch calling (load shops from CSV, run batch calls, log outcomes)
- Case study generation (build case studies from real campaign data)
- Reporting (score scripts against conversion rates)

## Tools Connected (4+)
- **Ollama** — local AI for generating script variants (cheap, runs locally)
- **Google Search / Google Business Profile** — prospect discovery, phone number verification
- **Deerflow** — workflow orchestration for calling campaigns
- **SQLite** — script storage, baseline scores, call outcomes, campaign data
- **Ops Digest** — publishes signals to portfolio-wide notification system

## Autonomous Decisions
- **Script generation**: Ollama generates multiple script variants for different contexts
- **Scoring**: scripts are scored against baseline before calls are made
- **Outcome tracking**: system logs what happened (booked, declined, no_answer, hung_up)
- **Script optimization**: tracks which scripts convert best, feeds back into generation
- **Batch calling**: loads verified shops from CSV, runs batch calls, logs all outcomes
- **Case study building**: automatically generates case studies from successful campaigns

## Daily Cadence
Runs on scheduled outreach cycles:
1. **Prospect discovery**: scrape Google Search/GBP for verified shops
2. **Script generation**: Ollama generates script variants
3. **Scoring**: score scripts against baseline before calling
4. **Batch calling**: load shops from CSV, run batch calls via call_executor
5. **Outcome logging**: log what happened (booked, declined, no_answer, hung_up)
6. **Reporting**: generate reports on script performance vs. conversion
7. **Case studies**: build case studies from successful campaigns

The system runs continuously, getting smarter with every campaign. Scripts that convert well are used more often. Scripts that don't convert are retired.

## Context Across Sessions
SQLite stores:
- Script variants (all versions of scripts, with context)
- Baseline scores (pre-call scoring for each script)
- Call outcomes (what happened on every call)
- Campaign data (which shops were called, when, what script was used)
- Case studies (generated from successful campaigns)

Every campaign has full context: what scripts were used, what the baseline scores were, what the outcomes were, what converted.

## CLI Commands
```bash
# Add a script variant
python -m phase3.cli add-script --name opener-a --context phone --file opener.txt

# List all scripts and their scores
python -m phase3.cli list

# Score a script before calling
python -m phase3.cli score 1 --backend manual --total 72 --humanity pass

# Log a call outcome
python -m phase3.cli log-outcome 1 --business "Ray's Body Shop" --outcome booked

# Generate a report
python -m phase3.cli report

# Batch call shops from CSV
python -m phase3.cli batch-call 1 --csv prospects.csv --limit 10

# Generate a case study
python -m phase3.cli case-study 1 --out case-study.md
```

## Integration with Portfolio
Publishes signals to ops digest:
- `did` signals when scripts are generated, calls are made, outcomes logged
- `needs_you` signals when scripts need review or campaigns need attention

The ops digest monitors agentic-priming daily and reports campaign status.

## Scoring
- **Qualifying**: 10 points (autonomous agent doing real work)
- **Complex**: 15 points (orchestrates 4+ tools, makes autonomous decisions, holds context, runs on scheduled cycles)
- **Total**: 25 points

## What Makes This Different
This isn't a "generate one email and send it" system. This is a full sales pipeline that:
- Finds prospects autonomously
- Generates multiple script variants
- Scores them before calling
- Tracks what actually converts
- Gets smarter over time
- Builds case studies from real data

The system is designed to run continuously, not as a one-off demo. Every campaign feeds back into the next one.
