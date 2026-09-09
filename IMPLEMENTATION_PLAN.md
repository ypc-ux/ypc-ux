# Implementation Plan: Sports Media Automation System

## Overview

This is the technical roadmap for building and deploying a complete podcast growth automation system in 4 weeks. The system automates 4 parallel campaigns using Brainwash OS (brand framework), Agentic Priming (discovery/verification), and Deerflow (orchestration).

---

## Architecture

### **Components**

```
┌─────────────────────────────────────────────────────────┐
│         Brand Setup Quiz (21st.dev UI)                  │
│         ↓ Captures podcast identity + values            │
├─────────────────────────────────────────────────────────┤
│  Brainwash OS Processor                                 │
│  ↓ Converts quiz → campaign contexts (4 docs)          │
├─────────────────────────────────────────────────────────┤
│  Agentic Priming Discovery (Phase 1/2, parallel)       │
│  ├─ Sponsorship discovery                              │
│  ├─ Guest discovery                                     │
│  ├─ Audience discovery                                  │
│  └─ Partnership discovery                               │
│  ↓ Contact verification (phone/email)                  │
├─────────────────────────────────────────────────────────┤
│  Script Generation (Ollama)                             │
│  ├─ 3–5 variants per campaign                          │
│  ├─ Brand-aware (using Brainwash OS)                   │
│  └─ Adapted weekly from outcomes                        │
├─────────────────────────────────────────────────────────┤
│  Deerflow Orchestration                                 │
│  ├─ Daily discovery runs (9 AM)                        │
│  ├─ Batch outreach (20 contacts/campaign/day)          │
│  └─ Outcome logging (SQLite)                           │
├─────────────────────────────────────────────────────────┤
│  Dashboard (Flask)                                      │
│  ├─ Real-time campaign status                          │
│  ├─ Prospect pipeline visualization                     │
│  ├─ Conversion analytics                               │
│  └─ Manual override buttons                             │
├─────────────────────────────────────────────────────────┤
│  Integrations                                           │
│  ├─ Slack (weekly digests)                             │
│  ├─ Discord (real-time alerts)                         │
│  ├─ Google Sheets (auto-sync)                          │
│  └─ GitHub Issues (follow-ups)                         │
├─────────────────────────────────────────────────────────┤
│  Deerflow GitHub Crawler                               │
│  ├─ Scans your repos for integrations                  │
│  └─ Proposes new integrations via PRs                  │
└─────────────────────────────────────────────────────────┘
```

### **Data Flow**

1. **Setup Phase**: Quiz → Brainwash OS processor → Campaign contexts
2. **Discovery Phase**: Agentic Priming finds prospects → Verification → Database
3. **Generation Phase**: Ollama generates scripts from context + feedback
4. **Execution Phase**: Deerflow queues and executes outreach → Logs outcomes
5. **Monitoring Phase**: Dashboard + weekly digests from database
6. **Learning Phase**: Analyze outcomes → Adapt scripts → Loop back to execution

---

## 4-Week Implementation Timeline

### **Week 1: Foundation & Brand Setup**

**Deliverables:**
- ✅ Setup quiz UI (21st.dev) deployed and tested
- ✅ Brainwash OS processor (converts quiz answers → campaign contexts)
- ✅ Campaign context documents auto-generated
- ✅ SQLite database schema initialized
- ✅ `.campaigns/` directory structure created

**Effort:** 40 hours  
**What happens:**
1. Build 21st.dev interactive quiz (5 question blocks, progress bar, smooth animations)
2. Create Python processor to parse quiz JSON → Brainwash OS 7-layer format
3. Auto-generate 4 campaign context docs (sponsorship, guests, audience, partnerships)
4. Initialize database schema (scripts, campaigns, attempts, outcomes)
5. Test end-to-end: complete quiz → see generated context docs

**Deliverable Test:**
```bash
bash scripts/setup-quiz.sh
# Answer quiz → generates .campaigns/sponsorship.md, guests.md, etc.
# Verify campaign contexts feel authentic to podcast brand
```

---

### **Week 2: Campaign Discovery & Verification**

**Deliverables:**
- ✅ Agentic Priming Phase 1/2 adapted for 4 campaigns (parallel)
- ✅ Contact discovery engine running for all 4 campaigns
- ✅ Phone/email verification at scale
- ✅ First prospects loaded into database
- ✅ Campaign CSV output (prospects.csv per campaign)

**Effort:** 40 hours  
**What happens:**
1. Adapt existing `pipeline.py` for 4 campaign types (different search strategies)
   - Sponsorship: "sports brands + equipment companies near {ZIP}"
   - Guests: "{sports focus} athletes, coaches, experts"
   - Audience: "sports communities, {sports focus} enthusiasts"
   - Partnerships: "gyms, sports bars, local teams in {RADIUS}"
2. Run discovery in parallel (async) so all 4 campaigns finish simultaneously
3. Verify contacts: website scraping + LinkedIn (optional) + Yelp (if available)
4. Deduplicate across campaigns (same person won't be contacted 4x)
5. Load verified contacts into database with relevance scores

**Deliverable Test:**
```bash
python -c "from campaigns import discover_all; \
  discover_all(podcast_data, output='prospects_verified.csv')"
# Expect: ~85 prospects discovered, ~67 verified, CSV saved
```

---

### **Week 3: Script Generation & Deerflow Setup**

**Deliverables:**
- ✅ Ollama script generation pipeline
- ✅ 3–5 script variants per campaign (brand-aware)
- ✅ Deerflow workflow YAML configured
- ✅ GitHub repo crawler ready
- ✅ First batch outreach queued (but not sent yet)

**Effort:** 40 hours  
**What happens:**
1. Build Ollama script generation module (`ollama_script_gen.py`):
   - Input: campaign context + Brainwash OS data + past feedback
   - Output: 3–5 distinct script variants with metadata
   - Use temperature=0.7 for creative variety
   - Validate scripts are coherent before storing in DB
2. Create Deerflow workflow (`deerflow_workflow.yaml`):
   - Trigger: Daily 9 AM (configurable)
   - Steps: Load prospects → Generate scripts → Score baselines → Queue outreach → Log outcomes
   - Parallel execution: all 4 campaigns simultaneously
3. Build GitHub repo crawler (Deerflow plugin):
   - Scan friend's repos for existing integrations (Slack, Discord, etc.)
   - Identify integration opportunities
   - Create PR with recommended config
4. Queue first batch (20 contacts per campaign) but hold execution for manual review

**Deliverable Test:**
```bash
deerflow run deerflow_workflow.yaml --dry-run
# Expect: Workflow executes (dry-run), generates scripts, queues outreach
# Verify: Scripts are coherent and campaign-specific
```

---

### **Week 4: Dashboard, Integrations & Go-Live**

**Deliverables:**
- ✅ Flask dashboard live (real-time campaign status)
- ✅ All integrations connected (Slack, Discord, Sheets, GitHub)
- ✅ Weekly digest automation running
- ✅ Full system deployed and monitoring
- ✅ First outcomes logged (real contacts responding)

**Effort:** 40 hours  
**What happens:**
1. Build Flask dashboard:
   - Real-time view of all 4 campaigns (prospects contacted, responses, bookings)
   - Prospect pipeline visualization (discovery → verified → contacted → booked)
   - Conversion metrics per campaign + per script
   - Manual override buttons (skip prospect, use custom script, mark as booked)
   - Weekly digest preview
2. Connect integrations:
   - **Slack**: Weekly digest → your channel (Monday 8 AM)
   - **Discord**: Real-time alerts → your server (prospect booked, new lead quality)
   - **Google Sheets**: Auto-sync verified contacts + outcomes (shared sheet)
   - **GitHub Issues**: Auto-create follow-up tasks (for prospects that need re-contact)
3. Enable full automation:
   - Deerflow runs daily (9 AM): discovery → verification → script generation → outreach
   - Database logs all interactions
   - Dashboard updates real-time
   - Weekly digest sends automatically
4. Execute GitHub crawler:
   - Create first PR with integration recommendations
   - Friend reviews + approves merge
   - Integrations auto-activate from config

**Deliverable Test:**
```bash
# Start Deerflow
deerflow serve deerflow_workflow.yaml

# In separate terminal: open dashboard
python dashboard/app.py

# Verify: Campaigns running, outcomes logging, digest preview works
```

---

## Technology Stack

| Component | Technology | Why |
|---|---|---|
| **Quiz UI** | 21st.dev | Animated, non-technical, fast |
| **Brand Processing** | Python + Brainwash OS framework | Structured, reusable |
| **Discovery** | Agentic Priming Phase 1/2 | Battle-tested, already built |
| **Verification** | Website scraping + optional APIs | Free, no dependencies |
| **Script Generation** | Ollama (mistral model) | Local, free, adapts from feedback |
| **Orchestration** | Deerflow | Workflow automation + GitHub crawler |
| **Database** | SQLite | Lightweight, zero maintenance |
| **Dashboard** | Flask + Chart.js | Simple, real-time, zero-cost |
| **Integrations** | Slack SDK, Discord SDK, Sheets API | Official libraries, reliable |
| **Version Control** | GitHub | Recommendations via PRs |

### **New Dependencies**
- `brainwashos` (Brainwash OS framework, installed via skill)
- `ollama` (Python client)
- `pyyaml` (Deerflow workflow parsing)
- `slack-sdk` (Slack integration)
- `discord.py` (Discord integration)
- `google-auth-oauthlib`, `google-sheets` (Sheets sync)
- `flask`, `flask-cors` (Dashboard)

---

## Database Schema

### **campaigns** table
```sql
CREATE TABLE campaigns (
  id INTEGER PRIMARY KEY,
  podcast_id TEXT,
  campaign_type TEXT,  -- 'sponsorship'|'guests'|'audience'|'partnerships'
  status TEXT,         -- 'active'|'paused'|'completed'
  created_at TIMESTAMP
);
```

### **prospects** table
```sql
CREATE TABLE prospects (
  id INTEGER PRIMARY KEY,
  campaign_id INTEGER,
  name TEXT,
  contact_info TEXT,  -- Email or phone
  relevance_score REAL,  -- 0.0-1.0
  verified BOOLEAN,
  source TEXT,        -- 'google_search'|'yelp'|'linkedin'
  created_at TIMESTAMP
);
```

### **scripts** table
```sql
CREATE TABLE scripts (
  id INTEGER PRIMARY KEY,
  campaign_id INTEGER,
  variant_num INTEGER,  -- 1, 2, 3, etc.
  body TEXT,
  created_at TIMESTAMP
);
```

### **outcomes** table
```sql
CREATE TABLE outcomes (
  id INTEGER PRIMARY KEY,
  prospect_id INTEGER,
  script_id INTEGER,
  outcome TEXT,  -- 'booked'|'declined'|'no_answer'|'follow_up'
  notes TEXT,
  contacted_at TIMESTAMP
);
```

### **integrations** table
```sql
CREATE TABLE integrations (
  id INTEGER PRIMARY KEY,
  type TEXT,        -- 'slack'|'discord'|'sheets'|'github_issues'
  config JSON,      -- Integration-specific config
  enabled BOOLEAN,
  created_at TIMESTAMP
);
```

---

## File Structure

```
sports-media-automation/
├── setup-quiz.html              # 21st.dev interactive quiz
├── campaigns/
│   ├── config.json              # Campaign parameters (generated by setup)
│   ├── sponsorship.md           # Auto-generated context
│   ├── guests.md
│   ├── audience.md
│   └── partnerships.md
├── agentic_priming_pilot/
│   ├── pipeline.py              # Phase 1/2 discovery (adapted for 4 campaigns)
│   ├── ollama_script_gen.py      # Script generation module
│   ├── deerflow_workflow.yaml    # Orchestration workflow
│   └── requirements.txt
├── dashboard/
│   ├── app.py                   # Flask dashboard
│   ├── templates/
│   │   ├── index.html           # Dashboard UI
│   │   └── digest_preview.html  # Weekly digest preview
│   └── static/
│       ├── style.css
│       └── chart.js
├── integrations/
│   ├── slack.py                 # Slack integration
│   ├── discord.py               # Discord integration
│   ├── sheets.py                # Google Sheets sync
│   └── github_issues.py          # GitHub Issues creation
├── scripts/
│   ├── setup-quiz.sh            # Launch quiz
│   ├── run-campaigns.sh          # Start Deerflow
│   └── check-status.sh           # Dashboard + integrations
├── pilot.db                     # SQLite database (auto-created)
└── README.md, PRODUCT_PACKAGE.md, VALUE_BREAKDOWN.md
```

---

## Deployment Checklist

### **Pre-Launch**
- [ ] Quiz works and outputs valid JSON
- [ ] Campaign contexts generated and readable
- [ ] Discovery runs on test data (finds prospects)
- [ ] Verification works (narrows to verified contacts)
- [ ] Scripts generated and stored in database
- [ ] Deerflow workflow parses and runs (dry-run)
- [ ] Dashboard displays test data
- [ ] Slack/Discord integrations authenticate
- [ ] Google Sheets sync works
- [ ] All documentation written and reviewed

### **Launch**
- [ ] Real podcast data loaded into setup quiz
- [ ] Deerflow scheduled for daily 9 AM run
- [ ] Integrations enabled and tested (send test Slack message, Discord alert)
- [ ] Dashboard monitoring active
- [ ] First batch of 20 prospects queued per campaign (80 total)
- [ ] Database logging all interactions
- [ ] Weekly digest preview working

### **Post-Launch (Week 4+)**
- [ ] First outcomes logged (responses, bookings)
- [ ] Script adaptation triggered after 10+ attempts
- [ ] Weekly digest sent (Monday 8 AM)
- [ ] Dashboard showing real metrics
- [ ] Deerflow running automatically (no manual intervention)

---

## Success Metrics (Week 4+)

| Metric | Target | Acceptable Range |
|---|---|---|
| Prospects discovered/week | 85 | 60–100 |
| Prospects verified | 80% | 75–90% |
| Contacts reached/week | 20 per campaign | 15–25 |
| Initial conversion rate | 5–10% | 3–15% |
| Script adaptation happening | Yes | Every 2–3 weeks |
| Dashboard uptime | 99% | >95% |
| Integrations working | All | 3 out of 4 minimum |
| Weekly digest sending | Yes | On time, accurate |

---

## Rollback Plan

If something breaks:

1. **Quiz not working**: Disable, use manual JSON input file
2. **Discovery fails**: Fall back to manual prospect list CSV
3. **Verification issues**: Skip verification, use all discovered prospects
4. **Script generation fails**: Use default templates from database
5. **Deerflow breaks**: Pause automation, manually trigger individual campaigns
6. **Dashboard down**: View database directly with `sqlite3 pilot.db`
7. **Integration errors**: Disable failing integration, others still run

All fallbacks are documented and can be activated in <1 hour.

---

## Next Steps

1. **Gather friend's podcast details** (name, listener count, sports focus, pain points)
2. **Finalize campaign prioritization** (which of the 4 are highest priority?)
3. **Choose integrations** (Slack? Discord? Google Sheets?)
4. **Start Week 1** (build setup quiz + Brainwash OS processor)

---

## Support & Maintenance

**During Implementation (4 weeks):**
- Weekly check-ins (30 min each)
- Slack channel for urgent questions
- Documentation as you go

**After Launch (Month 2+):**
- Monthly check-ins (optional)
- Roadmap alignment (what features to build next)
- Bug fixes and optimization
- Script adaptation tuning

---

*This plan is detailed but flexible. We'll adjust based on your friend's feedback after Week 1.*
