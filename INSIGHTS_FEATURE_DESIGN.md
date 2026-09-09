# Insights & Recommendations: Customer Value Feature Design

**Date**: September 2026  
**Status**: Design Phase (Implementation: Next Sprint)  
**Priority**: Primary (User Request)  
**Audience**: Agentic Priming pilot users running their own local campaigns  

---

## Executive Summary

**Feature Goal**: Auto-generate actionable insights from Phase 3 call outcomes to help users understand what's working, what's not, and how to improve.

**Core Insight**: After ~30 call attempts, patterns emerge (which scripts convert better, which objections dominate, which geographic areas book more). We can detect these patterns automatically and surface them in a "Key Insights" section of the case study.

**Value Proposition**: Instead of users manually reading 50 call logs and guessing "what worked," we tell them:
- "Your opener angle #2 converts better (38% vs 22%)"
- "Shops in 30035 zip book 3x more than 30024"
- "Tuesday mornings have highest answer rates"
- "These 5 objections account for 80% of declines"

---

## Phase 3 Data Inventory

### What We Have (from pilot.db)
```
attempts table:
  - script_version_id (which script variant used)
  - business_name (shop name)
  - phone (shop phone)
  - outcome (booked, declined, no_answer, hung_up, wrong_number, disconnected)
  - channel (phone, in_person)
  - notes (objection text, outcome reason, etc.)
  - contacted_at (timestamp)

script_versions table:
  - id, name, context (phone vs in_person)
  - body (the actual script text)

baselines table:
  - script_version_id, total_score (87-heuristic score)
```

### What We Can Extract

| Data Source | Insight Type | Example |
|-------------|--------------|---------|
| **attempts.outcome** | Script performance | "Script A booked 38%, Script B booked 22%" |
| **attempts.notes** | Objections + objection patterns | "Top 5 objections: price (18%), no time (15%), don't need work (12%)..." |
| **attempts.contacted_at** | Temporal patterns | "Tuesday 10am–2pm highest answer rate (72%)" |
| **script_versions.body** | Script angle analysis | "Scripts emphasizing ROI convert better than urgency" |
| **shops.zip** (Phase 1/2) | Geographic patterns | "30035 zip books 3× higher than 30024" |
| **attempts.channel** | Channel comparison | "Phone: 45% booking rate, In-person: 62% (if applicable)" |
| **baselines.total_score** | Score vs outcome correlation | "High-scoring scripts (80+) convert at 35%, low-scoring (60-) at 18%" |

---

## Insight Categories (MVP)

### Category 1: Script Performance Comparison
**What**: Which script variant performs best?
**How**: Compare booking rate across script_version_id
**Output**: 
```
📊 Script Performance Ranking
1. "Opener #2" (value-focused)   → 38% booking rate (8/21 attempts)
2. "Opener #1" (urgency-focused) → 22% booking rate (4/18 attempts)

Recommendation: Emphasize value proposition; current urgency angle underperforms.
```

**SQL**:
```sql
SELECT 
  sv.name,
  sv.id,
  COUNT(*) as total_attempts,
  SUM(CASE WHEN a.outcome = 'booked' THEN 1 ELSE 0 END) as booked_count,
  ROUND(100.0 * SUM(CASE WHEN a.outcome = 'booked' THEN 1 ELSE 0 END) / COUNT(*), 1) as booking_rate
FROM attempts a
JOIN script_versions sv ON a.script_version_id = sv.id
GROUP BY sv.id, sv.name
ORDER BY booking_rate DESC;
```

### Category 2: Top Objections & Decline Patterns
**What**: What reasons do people decline?
**How**: NLP on attempts.notes; count common objection phrases
**Output**:
```
⚠️ Top Decline Reasons (18 declined attempts)
1. "No time" / "Too busy" → 7 instances (39%)
2. "Don't need work" / "Already have a guy" → 4 instances (22%)
3. "Price too high" / "Too expensive" → 3 instances (17%)
4. Other → 4 instances (22%)

Recommendation: Create response script for "too busy" objection; emphasize speed/convenience.
```

**Implementation**:
```python
def extract_objections(conn):
    attempts = conn.execute(
        "SELECT notes FROM attempts WHERE outcome = 'declined' AND notes != ''"
    ).fetchall()
    
    objection_keywords = {
        "no_time": ["busy", "time", "later", "call back"],
        "no_need": ["don't need", "already have", "not interested"],
        "price": ["expensive", "price", "cost", "afford"],
        "unavailable": ["not available", "closed", "moved"],
    }
    
    matches = Counter()
    for (note,) in attempts:
        for category, keywords in objection_keywords.items():
            if any(kw in note.lower() for kw in keywords):
                matches[category] += 1
    
    return matches.most_common()
```

### Category 3: Geographic Performance
**What**: Do shops in certain zips convert better?
**How**: Join attempts with shops (Phase 1/2 CSV), group by zip
**Output**:
```
📍 Geographic Performance (by zip code)
1. 30035 (Decatur)   → 42% booking rate (10/24 attempts)
2. 30308 (Midtown)   → 28% booking rate (4/14 attempts)
3. 30303 (Downtown)  → 17% booking rate (1/6 attempts)

Recommendation: Focus calling efforts on Decatur area; higher ROI. Note: sample size for Downtown is small.
```

**Implementation**:
```python
def geographic_analysis(conn, shops_csv_path):
    # Load shops from Phase 1/2 CSV
    shops = load_shops_csv(shops_csv_path)
    shop_map = {shop['phone_gbp']: shop['zip'] for shop in shops}
    
    # Join attempts with zips
    attempts = conn.execute(
        "SELECT phone, outcome FROM attempts WHERE outcome IN ('booked', 'declined', 'no_answer')"
    ).fetchall()
    
    by_zip = Counter()
    booked_by_zip = Counter()
    
    for phone, outcome in attempts:
        zip_code = shop_map.get(phone, "unknown")
        by_zip[zip_code] += 1
        if outcome == "booked":
            booked_by_zip[zip_code] += 1
    
    results = []
    for zip_code, count in by_zip.most_common():
        booked = booked_by_zip[zip_code]
        rate = 100.0 * booked / count
        results.append((zip_code, rate, booked, count))
    
    return results
```

### Category 4: Temporal Patterns
**What**: Which days/times have highest answer rates?
**How**: Extract hour-of-day and day-of-week from attempted_at timestamp
**Output**:
```
⏰ Best Time to Call
- Day of week: Tuesday–Thursday (48% answer rate vs 35% Mon/Fri)
- Hour of day: 10am–12pm (52% answer rate) and 2pm–4pm (49% answer rate)
- Worst: 8–9am (22%), 12–1pm (lunch, 28%)

Recommendation: Schedule calls Tue–Thu, 10–12am or 2–4pm for best results.
```

**Implementation**:
```python
from datetime import datetime

def temporal_analysis(conn):
    attempts = conn.execute(
        "SELECT contacted_at, outcome FROM attempts WHERE outcome != 'no_answer'"
    ).fetchall()
    
    # Hour of day analysis
    hour_stats = defaultdict(lambda: {"total": 0, "answered": 0})
    for contacted_at, outcome in attempts:
        dt = datetime.fromisoformat(contacted_at)
        hour = dt.hour
        hour_stats[hour]["total"] += 1
        if outcome != "no_answer":
            hour_stats[hour]["answered"] += 1
    
    hour_results = [
        (hour, 100.0 * stats["answered"] / stats["total"])
        for hour, stats in hour_stats.items()
    ]
    
    # Day of week analysis (similar pattern)
    
    return sorted(hour_results, key=lambda x: x[1], reverse=True)
```

### Category 5: Score vs Outcome Correlation
**What**: Do higher-scored scripts actually book more?
**How**: Join baselines with attempts, compare score ranges to booking rate
**Output**:
```
📈 Baseline Score vs Booking Rate
- Score 80+  (premium scripts)   → 35% booking rate (7/20 attempts)
- Score 60–79 (good scripts)     → 24% booking rate (6/25 attempts)
- Score <60  (needs work)        → 12% booking rate (1/8 attempts)

Analysis: Scoring is predictive! 80+ scripts book ~3× more.
Recommendation: Focus on high-scoring angles; deprioritize low-scoring variants.
```

**Implementation**:
```python
def score_outcome_correlation(conn):
    results = conn.execute("""
        SELECT 
            b.total_score,
            a.outcome,
            COUNT(*) as count
        FROM attempts a
        JOIN script_versions sv ON a.script_version_id = sv.id
        LEFT JOIN baselines b ON sv.id = b.script_version_id
        WHERE b.total_score IS NOT NULL
        GROUP BY b.total_score, a.outcome
    """).fetchall()
    
    # Bucket scores and compute booking rate per bucket
    buckets = defaultdict(lambda: {"total": 0, "booked": 0})
    for score, outcome, count in results:
        bucket = "80+" if score >= 80 else ("60-79" if score >= 60 else "<60")
        buckets[bucket]["total"] += count
        if outcome == "booked":
            buckets[bucket]["booked"] += count
    
    return buckets
```

---

## Insights Presentation: Case Study Integration

### Where Insights Go
**Current case study structure** (`case_study_md`):
```markdown
# Case Study: Agentic Priming Pilot Results
- Executive Summary
- Booking Rate with Wilson CI
- Script Variant Comparison
- Data by Attempt
```

**NEW: Insert "Key Insights" section**:
```markdown
# Case Study: Agentic Priming Pilot Results

## Executive Summary
[Existing booking rate + Wilson CI]

## 🔑 Key Insights & Recommendations
[NEW: Auto-generated insights from categories 1–5]
- Script Performance: [Top performer + weak performer]
- Top Objections: [Ranked list + suggested responses]
- Geographic Hotspots: [Best-performing zips]
- Best Times to Call: [Hour + day recommendations]
- Score Predictiveness: [Does baseline score correlate with outcomes?]

## Booking Rate with Statistical Confidence
[Existing content]

## Script Variant Comparison
[Existing content]

## Detailed Attempt Log
[Existing content]
```

### Example Output (Generated Automatically)
```markdown
## 🔑 Key Insights & Recommendations

### 1. Script Performance
**Top Performer**: Opener #2 (Value Focus)  
- Booking rate: **38%** (8 of 21 attempts booked)
- Script focus: ROI, time savings, competitive advantage

**Runner-Up**: Opener #1 (Urgency Focus)  
- Booking rate: 22% (4 of 18 attempts)
- Script focus: Market pressure, limited time

**Insight**: Value-focused opener converts 73% better than urgency-focused. 
**Action**: Regenerate scripts emphasizing ROI and business impact over FOMO.

### 2. Top Decline Reasons
1. **"No time / Too busy"** (39% of declines, 7 instances)
   - Suggested response: "I can work around your schedule. 15-minute quick assessment?"
   
2. **"Don't need work / Already have a guy"** (22%, 4 instances)
   - Suggested response: "No problem. Might I be a backup option? Here's my card."
   
3. **"Price concerns"** (17%, 3 instances)
   - Suggested response: "Quality and speed matter more than price. Can I show you the difference?"

### 3. Geographic Performance
**Hotspot**: 30035 (Decatur)  
- Booking rate: 42% (10 of 24 attempts)
- Recommendation: Allocate 50% of next calling round to this zip code

**Underperformer**: 30303 (Downtown)  
- Booking rate: 17% (1 of 6 attempts)
- Note: Small sample size; needs more attempts before judgment

### 4. Best Time to Call
**Optimal window**: **Tuesday–Thursday, 10–12am or 2–4pm**  
- Answer rate: 48–52%
- Booking rate: 38–42%

**Avoid**: Monday/Friday mornings (35% answer rate), 12–1pm lunch (28%)

### 5. Script Scoring is Predictive
**Finding**: Higher-scored scripts (80+) convert 3× better  
- 80+ score → 35% booking
- 60–79 score → 24% booking  
- <60 score → 12% booking

**Confidence**: Yes; baseline score is a useful indicator of real-world performance.

---

## Next Steps

1. Calling round 2: Focus on 30035 zip, Tue–Thu, 10–12am
2. Respond to "too busy" objection: Add response in next script iteration
3. Generate new scripts with higher baseline scores (target 80+)
4. Increase calling volume to reduce geographic sample size variance
```

---

## Implementation Roadmap

### MVP (This Sprint)
- ✅ Design document (this file)
- Skeleton functions for insights extraction (1 hour)
  - `script_performance()` → SQL query
  - `top_objections()` → keyword matching
  - `geographic_analysis()` → zip code grouping
  - `temporal_analysis()` → hour-of-day bucketing
  - `score_correlation()` → score range binning

### Phase 1 (Next Sprint)
- Integrate into `case_study_generation()` function (2 hours)
- Add Markdown formatting
- Test with 50+ attempt dataset
- Validate insights are accurate + actionable

### Phase 2 (Q1 2025)
- Visualizations: matplotlib/plotly charts
- Export to PDF with charts embedded
- Email delivery: Auto-email case study + insights
- Slack integration: Post key insights to Slack channel

---

## Technical Integration Points

### File to Modify: `phase3/case_study_gen.py`
```python
def generate_case_study(conn, shops_csv_path, output_path):
    """Generate case study with insights."""
    
    # Existing logic
    attempts = fetch_attempts(conn)
    booking_rate = calculate_booking_rate(attempts)
    ci = wilson_score_ci(booking_rate, len(attempts))
    
    # NEW: Generate insights
    insights = {
        "script_performance": script_performance_analysis(conn),
        "objections": extract_top_objections(conn),
        "geography": geographic_analysis(conn, shops_csv_path),
        "timing": temporal_analysis(conn),
        "score_correlation": score_outcome_correlation(conn),
    }
    
    # Format into Markdown
    md = f"""
    # Case Study: Agentic Priming Pilot Results
    
    ## Executive Summary
    [Booking rate + Wilson CI]
    
    ## Key Insights & Recommendations
    {format_insights(insights)}
    
    ## Booking Rate with Statistical Confidence
    [Existing content]
    
    ... rest of case study ...
    """
    
    with open(output_path, "w") as f:
        f.write(md)
```

### File to Modify: `phase3/store.py`
```python
def extract_top_objections(conn, limit=5):
    """Extract top decline reasons from attempt notes."""
    # Implementation: keyword matching on declined attempts
    
def geographic_analysis(conn, shops_csv_path):
    """Analyze booking rate by zip code."""
    # Implementation: join attempts with shops, group by zip
    
def temporal_analysis(conn):
    """Analyze answer rate and booking rate by hour-of-day, day-of-week."""
    # Implementation: timestamp parsing, grouping
    
def score_outcome_correlation(conn):
    """Analyze whether baseline scores predict outcomes."""
    # Implementation: join baselines with outcomes, bucket scores
```

---

## Data Validation & Safeguards

### Minimum Thresholds
Insights should only be generated if:
- **Script Performance**: ≥5 attempts per variant (avoid small-sample noise)
- **Objections**: ≥10 declined attempts (minimum for pattern detection)
- **Geography**: ≥5 attempts per zip code (avoid geographic noise)
- **Timing**: ≥30 total attempts (enough data for hour-of-day patterns)
- **Score Correlation**: ≥20 scored scripts (minimum for correlation)

### Confidence Warnings
```python
def add_confidence_notes(insights, attempt_count):
    """Add caveats to low-confidence insights."""
    
    if attempt_count < 30:
        insights["_warning"] = (
            "Note: Fewer than 30 attempts. Sample size is small; "
            "insights may not be statistically significant."
        )
    
    if insights["geography"]["total_zips"] < 3:
        insights["geography"]["_warning"] = (
            "Geographic analysis based on <3 zip codes; limited geographic diversity."
        )
    
    return insights
```

### Presentation in Case Study
```markdown
⚠️ **Note**: This case study is based on 28 attempts across 2 zip codes and 2 script 
variants. Sample size is approaching statistical significance threshold (30). 
Insights are directional but not definitive; continue calling for stronger signal.
```

---

## Example Output: Full Insights Section

```markdown
## 🔑 Key Insights & Recommendations (This Week's Pilot)

Based on 47 calling attempts across 24 shops, 3 zip codes, and 2 script variants.

### Script Performance Ranking

| Rank | Script | Booking Rate | Attempts | Status |
|------|--------|--------------|----------|--------|
| 1️⃣ | Opener #2: Value Focus | **38%** (8/21) | 21 | ✅ Use this |
| 2️⃣ | Opener #1: Urgency Focus | 22% (4/18) | 18 | ⚠️ Needs work |

**Insight**: Value-focused opener converts 73% better. **Action**: Regenerate scripts focusing on ROI and business efficiency.

### Common Decline Reasons (18 declines)

1. **"No time / Too busy"** (39%, 7 times)
   - How to respond: "I can work around your schedule. 15-minute assessment?"

2. **"Don't need work / Already have a guy"** (22%, 4 times)
   - How to respond: "No problem. Might I be a backup option?"

3. **"Price too high"** (17%, 3 times)
   - How to respond: "Quality and speed matter more. Can I show the difference?"

**Insight**: "Too busy" is the #1 objection. **Action**: Prepare concise, time-efficient pitch emphasizing speed.

### Geographic Performance

**Best Zip**: 30035 (Decatur) → **42% booking** (10 of 24 attempts)  
**Runner-up**: 30308 (Midtown) → 28% booking (4 of 14 attempts)  
**Lagging**: 30303 (Downtown) → 17% booking (1 of 6 attempts, small sample)

**Insight**: Decatur area converts 2.5× better. **Action**: Allocate 60% of next calling round to Decatur zip code.

### Best Time to Call

**Sweet spot**: **Tue–Thu, 10–12pm or 2–4pm** (Answer rate: 48–52%)  
**Avoid**: Mon/Fri mornings (35%), 12–1pm lunch (28%)

**Insight**: Day of week and time of day matter significantly. **Action**: Schedule calls during optimal windows.

### Do High-Scoring Scripts Actually Convert Better?

**YES** — Baseline score predicts outcome.

| Score Range | Booking Rate | Data Points |
|-------------|--------------|-------------|
| 80+ (excellent) | **35%** | 20 attempts |
| 60–79 (good) | 24% | 22 attempts |
| <60 (needs work) | 12% | 5 attempts |

**Insight**: Higher-scored scripts book ~3× more. This validates the 87-heuristic scoring model. **Action**: Focus on scripts with baseline score 75+.

---

## Limitations & Future Enhancements

### Current Limitations (MVP)
- No multivariate analysis (e.g., "which combination of time + zip + script works best?")
- No time-series trend analysis (e.g., "booking rate improving/declining over time?")
- No cohort analysis (e.g., "shops with <2 employees respond differently")

### Future Enhancements (Phase 2)
- Predictive models: "If you call 100 more shops in Decatur on Tuesday, expect ~42 bookings"
- Cohort discovery: "Small shops (1–3 employees) respond better to price-focused scripts"
- A/B test significance: "Is 38% vs 22% statistically significant? (Yes, p < 0.05)"
- Sensitivity analysis: "If we improve answer rate by 10%, overall booking rate becomes X"

---

## Success Metrics

- ✅ Insights section generates without manual work
- ✅ Insights are actionable (lead to behavior change)
- ✅ Insights are accurate (validated against manual review)
- ✅ Users report higher confidence in decision-making
- ✅ Insights identify non-obvious patterns (user couldn't have figured out alone)

---

## Conclusion

The "Insights & Recommendations" feature transforms raw call data into actionable intelligence, enabling users to make informed decisions about which scripts to keep, when/where to call, and how to respond to objections. By auto-generating insights from the Phase 3 database, we reduce manual analysis burden and surface patterns that would be invisible in log files.

**Recommended implementation**: Design phase complete. Proceed to MVP implementation next sprint (2 hours) to integrate into case study generation.
