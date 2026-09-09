# Agentic Priming Stack: Efficiency Audit & Optimization Roadmap

**Date**: September 2026  
**Scope**: Phase 1/2 (discovery + verification) + Phase 3 (scoring + calling + feedback)  
**Goal**: Identify bottlenecks and recommend optimizations  

---

## Executive Summary

### Current Performance (Baseline)
- **Phase 1/2 runtime**: ~2–5 minutes per 50 shops (mostly Playwright waits)
- **Phase 3 runtime**: ~0.5–2 hours per iteration (call execution time varies)
- **Bottleneck**: Sequential operations dominate (one shop at a time, one variant at a time)

### Recommended Optimizations

| Priority | Phase | Bottleneck | Solution | Impact | Effort | Timeline |
|----------|-------|-----------|----------|--------|--------|----------|
| 🔴 HIGH | 1/2 | Playwright serial scraping | Batch 5 Playwright instances | 40–60% faster | 4 hours | Next sprint |
| 🔴 HIGH | 3 | Sequential Ollama generation | Parallel variant generation | 50–70% faster | 3 hours | Next sprint |
| 🟡 MED | 1/2 | Yelp API optional | Add web scraping fallback | 0% faster, $12–60/year savings | 2 hours | Q1 2025 |
| 🟡 MED | 3 | Manual script scoring | Cache baseline results | 30% fewer API calls | 1 hour | This sprint |
| 🟢 LOW | 3 | Batch size (10 shops) | Increase to 20–50 shops | 2× iteration speed | 30 min | Q1 2025 |
| 🟢 LOW | 1/2 | GBP scraping re-parsing | Cache JSON-LD results | 20% faster GBP scrapes | 1 hour | Q1 2025 |

### Recommended Implementation Order
1. **This Sprint** (1 hour): Cache baseline scores in Phase 3
2. **Next Sprint** (4–7 hours): Parallel Playwright + parallel Ollama
3. **Q1 2025**: Batch size increases + Yelp fallback + GBP caching

---

## Phase 1/2 Analysis: Shop Discovery & Verification

### Current Architecture
```
For each query ("auto body shop", "collision repair", "tire shop"):
  Step 1: Scrape Google Search (BeautifulSoup) → list of candidates
  Step 2: Fall back to Google Maps (Playwright) if <5 results
  Step 3: For each candidate:
    → Open GBP (Playwright)
    → Wait for JS rendering (2–3 seconds)
    → Parse JSON-LD, extract phone/rating
    → Scrape website for phone number (requests)
    → Check Yelp API if key set
    → Score confidence
```

### Bottleneck Analysis

#### 1. **Playwright Serial Scraping** (Primary Bottleneck)
**Current**: One GBP page loads at a time, waits 3–5 seconds for JS rendering
```
For each shop in candidates:
  browser.goto(gbp_url)
  wait for page.evaluate(js_snippet) [3–5 seconds]
  time.sleep(1) [rate limiting]
  browser.close()
```

**Problem**: 50 shops × 4 seconds = 200 seconds (~3.3 minutes) just waiting for pages

**Solution**: Batch Playwright instances (5 concurrent browsers)
```python
def gbp_scrape_details_batch(maps_urls: list, max_concurrent: int = 5):
    """Scrape multiple GBP pages in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {executor.submit(gbp_scrape_details, url): url for url in maps_urls}
        results = []
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return results
```

**Impact**: 200 seconds → ~50 seconds (75% reduction)
**Effort**: 4 hours (add threading, handle browser lifecycle)
**Risk**: Low (isolated, no state dependencies)

#### 2. **Google Search vs Maps Rate Limiting**
**Current**: Sleeps 1–2 seconds between requests
**Problem**: Google's rate limiting is reactive, not proactive; we sleep unnecessarily

**Solution**: Implement adaptive rate limiting (backoff on 429, normal speed otherwise)
```python
def scrape_with_backoff(url, max_retries=3):
    """Retry with exponential backoff on 429."""
    for retry in range(max_retries):
        try:
            resp = SESSION.get(url, timeout=10)
            if resp.status_code == 429:
                wait = 2 ** retry  # 1s, 2s, 4s
                log.warning("Rate limited; waiting %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            pass
    return None
```

**Impact**: 10–20% faster (depends on rate limiting frequency)
**Effort**: 1 hour
**Risk**: Low

#### 3. **GBP JSON-LD Re-Parsing**
**Current**: Parse JSON-LD from every GBP page every time
**Problem**: Same page scraped multiple times if re-run pipeline

**Solution**: Cache GBP results in SQLite (keyed by maps_url)
```python
# In gbp_scrape_details():
cached = gbp_cache.get(maps_url)
if cached:
    return cached

# ... scrape page ...

gbp_cache.set(maps_url, details)
return details
```

**Impact**: 20% faster on re-runs (first run unchanged)
**Effort**: 1 hour
**Risk**: Low (cache invalidation: TTL = 7 days)

#### 4. **Yelp API Dependency**
**Current**: Optional, but if key set, calls Yelp for every shop
**Problem**: $0.01–0.05 per call; already optional but slow fallback

**Solution**: Add Yelp web scraping fallback (future sprint)
```python
def yelp_lookup_web(name, address, zip_code):
    """Web scraping fallback when API unavailable."""
    query = f'site:yelp.com "{name}" {zip_code}'
    # Use existing Google Search scraping to find Yelp listing
    # Parse Yelp page to extract phone
    pass
```

**Impact**: $0/month (vs $12–60/year)
**Effort**: 2 hours
**Risk**: Medium (web scraping less reliable than API)
**Timeline**: Q1 2025

---

## Phase 3 Analysis: Scoring, Calling & Feedback Loop

### Current Architecture (Ollama + Deerflow Integrated)
```
1. Load shops CSV (Phase 1/2 output)
2. [Ollama] Generate 2 script variants
3. [Phase 3] Register in database
4. [Manual] Score each variant (user types numbers)
5. [Batch] Call 10 shops (simulated or real)
6. [Phase 3] Log outcomes
7. [Ollama] Analyze booking feedback
8. [Decision] If booking_rate < 30%, regenerate scripts
9. Loop back (until 50 attempts or manual stop)
```

### Bottleneck Analysis

#### 1. **Sequential Ollama Script Generation** (Primary)
**Current**: Generate scripts one at a time, wait for Ollama response
```python
def generate_scripts(context, num_variants=2, model="mistral"):
    scripts = []
    for i in range(num_variants):
        # Ollama inference: 2–5 seconds per variant
        response = ollama.generate(prompt, model=model)
        scripts.append(response)
    return scripts
```

**Problem**: 2 variants × 3 seconds = 6 seconds; add analysis at end = 10+ seconds total

**Solution**: Parallel generation (queue 5 variants to Ollama simultaneously)
```python
import threading

def generate_scripts_parallel(context, num_variants=5, model="mistral"):
    results = [None] * num_variants
    threads = []
    
    def gen_variant(idx):
        results[idx] = ollama.generate(prompt_for_angle(angles[idx]), model=model)
    
    for i in range(num_variants):
        t = threading.Thread(target=gen_variant, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    return results
```

**Impact**: 6 seconds → 1.5 seconds (75% reduction, assumes 4 threads max)
**Effort**: 2 hours
**Risk**: Low (Ollama handles threading)
**Note**: Requires Ollama running locally (not over network)

#### 2. **Manual Baseline Scoring Delay**
**Current**: User manually types score for each variant before calling
```
[Phase 3] Waiting for manual baseline...
User runs: python -m phase3.cli score <id> --backend manual --total 72 --humanity pass
```

**Problem**: Blocks entire workflow; human delay (hours/days)

**Solution**: Cache baseline scores in pilot.db
- First time: User scores variant
- Re-use: Automatically use cached score for identical/similar scripts
- Fallback: Auto-score with Ollama lightweight predictor (score_simple)

```python
def get_or_create_baseline(conn, script_id, context):
    baseline = store.latest_baseline(conn, script_id)
    if baseline:
        return baseline  # Cache hit
    
    # Not in cache; offer options:
    # 1. User scores manually
    # 2. Use Ollama quick-score (Likert scale, not actual calls)
    
    if os.environ.get("SCORER_BACKEND") == "http":
        # Call API
        return score_http(script_body, context)
    else:
        # Wait for manual
        print(f"Script {script_id} needs baseline. Run: python -m phase3.cli score {script_id} ...")
        return None
```

**Impact**: 30% fewer API calls on re-runs
**Effort**: 1 hour (add cache logic)
**Risk**: Low (backward compatible)

#### 3. **Batch Size Too Small (10 Shops)**
**Current**: Call 10 shops per iteration, then analyze
**Problem**: 50-attempt target requires 5 iterations; slow feedback loop

**Solution**: Increase batch size to 20–50 shops (if call system supports)
```
Before: 10 shops → log → analyze → regenerate → repeat
After:  50 shops → log → analyze → regenerate → done
```

**Impact**: Feedback loop 5× faster; fewer regeneration cycles
**Effort**: 30 minutes (change batch_size parameter)
**Risk**: Medium (depends on call system capacity)
**Timeline**: Q1 2025 (after call execution system is finalized)

#### 4. **Feedback Analysis Not Parallelized**
**Current**: `analyze_booking_feedback()` runs Ollama sequentially
```python
def analyze_booking_feedback(attempts):
    # Extract patterns one at a time
    summary = ollama.analyze(f"Summarize outcomes: {outcomes}")
    objections = ollama.analyze(f"Extract objections: {outcomes}")
    best_angle = ollama.analyze(f"Which angle worked best: {outcomes}")
    return {summary, objections, best_angle}
```

**Problem**: 3 Ollama calls × 2–3 seconds = 6–9 seconds

**Solution**: Parallel analysis
```python
from concurrent.futures import ThreadPoolExecutor

def analyze_booking_feedback_parallel(attempts):
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            "summary": executor.submit(lambda: ollama.analyze(summary_prompt)),
            "objections": executor.submit(lambda: ollama.analyze(objection_prompt)),
            "angle": executor.submit(lambda: ollama.analyze(angle_prompt)),
        }
        return {k: f.result() for k, f in futures.items()}
```

**Impact**: 6–9 seconds → 2–3 seconds (67% reduction)
**Effort**: 1 hour
**Risk**: Low
**Timeline**: Next sprint

---

## Performance Impact Summary

### Phase 1/2 Optimization Impact

| Optimization | Runtime | Memory | Throughput | Implementation |
|--------------|---------|--------|-----------|-----------------|
| Baseline (50 shops) | 3–5 min | ~200MB | 10–17 shops/min | - |
| + Playwright batching | 1–2 min | ~500MB | 25–50 shops/min | 4 hours, next sprint |
| + Adaptive rate limiting | 0.8–1.5 min | ~500MB | 33–60 shops/min | 1 hour, next sprint |
| + GBP caching | 0.8–1.5 min | ~600MB | 33–60 shops/min | 1 hour, Q1 2025 |
| **Net improvement** | **60% faster** | +400MB | **3–6× faster** | **6 hours total** |

### Phase 3 Optimization Impact

| Optimization | Runtime | API Calls | Throughput | Implementation |
|--------------|---------|-----------|-----------|-----------------|
| Baseline (50 attempts) | 10–15 min/iter | 5–10 | 3–5 attempts/min | - |
| + Parallel Ollama gen | 2–3 min/gen | 5–8 | 10–20 attempts/min | 2 hours, next sprint |
| + Script caching | 2–3 min/gen | 3–5 | 10–20 attempts/min | 1 hour, this sprint |
| + Parallel feedback analysis | 1–2 min/analysis | 3–5 | 15–30 attempts/min | 1 hour, next sprint |
| + Batch size 50 | 1 iteration total | 3–5 | 30–50 attempts/min | 30 min, Q1 2025 |
| **Net improvement** | **80% faster** | **40–50% fewer calls** | **10–50× faster** | **4.5 hours total** |

---

## Phase 1/2: Detailed Recommendations

### Immediate (This Sprint)
✅ None required; Numverify heuristic already implemented

### Short-Term (Next Sprint)
1. **Playwright Batching** (4 hours)
   - Modify `gbp_scrape_details()` to accept list of URLs
   - Create `gbp_scrape_details_batch(urls, max_workers=5)`
   - Update main loop to batch every 5 shops
   - Test with 50-shop run; verify 40–60% speedup

2. **Adaptive Rate Limiting** (1 hour)
   - Wrap `SESSION.get()` in retry loop
   - Catch 429, exponential backoff
   - Remove hardcoded `time.sleep()`

### Future (Q1 2025)
3. **GBP Caching** (1 hour)
   - Add cache table to pilot.db: `gbp_cache(maps_url, json_result, cached_at)`
   - TTL = 7 days (re-scrape if older)

4. **Yelp Web Scraping Fallback** (2 hours)
   - Use existing Google Search scraping to find Yelp listing
   - Parse Yelp page for phone number
   - Fallback only if API key not set

---

## Phase 3: Detailed Recommendations

### This Sprint (1–2 Hours)
1. **Script Caching** (1 hour)
   - In `get_or_create_baseline()`, check if variant already scored
   - If yes, reuse stored baseline
   - Reduces manual scoring workload on re-runs
   - See `phase3/store.py` for schema

### Next Sprint (3–4 Hours)
2. **Parallel Ollama Generation** (2 hours)
   - Modify `generate_scripts()` to spawn threads
   - Queue 5 variants simultaneously
   - Join all threads before returning
   - Test with 5 variant generation; verify 75% speedup

3. **Parallel Feedback Analysis** (1 hour)
   - Modify `analyze_booking_feedback()` to use ThreadPoolExecutor
   - Run summary, objections, angle extraction in parallel
   - Test after 30+ attempts; verify 67% speedup

4. **Increase Batch Size** (30 min)
   - Change `batch_size=10` to `batch_size=20`
   - Update `deerflow_workflow.yaml` step 4
   - Test with 50-shop batch

### Future (Q1 2025)
5. **Async Call Execution** (TBD)
   - Depends on call system (Twilio, etc.)
   - Currently simulated synchronously
   - When real dialer integrated, use async API

---

## Testing Plan: Performance Validation

### Phase 1/2 Optimization Testing
1. **Baseline measurement**:
   ```bash
   time python pipeline.py --zip 30035 --radius-miles 5 --limit 50
   # Expected: 3–5 minutes
   ```

2. **After Playwright batching**:
   ```bash
   time python pipeline.py --zip 30035 --radius-miles 5 --limit 50 --batch-scrape 5
   # Expected: 1–2 minutes (60% improvement)
   ```

3. **Verify accuracy**:
   - Compare output CSV with/without batching
   - Spot-check 10 rows for phone number correctness
   - Verify confidence scores match

### Phase 3 Optimization Testing
1. **Baseline measurement**:
   ```bash
   python -m phase3.cli test-perf --attempts 50 --iterations 1
   # Expected: 10–15 min per iteration
   ```

2. **After parallel Ollama**:
   ```bash
   OLLAMA_PARALLEL=5 python -m phase3.cli test-perf --attempts 50 --iterations 1
   # Expected: 2–3 min per iteration (75% improvement)
   ```

3. **After script caching**:
   ```bash
   # Run twice; second run should use cached baselines
   python -m phase3.cli test-perf --attempts 50 --iterations 2
   # Expected: 2nd iteration faster (cached baselines)
   ```

---

## Database Schema Changes Required

### Phase 1/2: GBP Cache
```sql
CREATE TABLE IF NOT EXISTS gbp_cache (
    maps_url TEXT PRIMARY KEY,
    json_result TEXT NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Phase 3: Script Baseline Cache
Already exists in `script_versions` + `baselines` tables; just add logic to check before calling scorer.

---

## Dependencies & Prerequisites

### Playwright Batching
- Python 3.8+ (for concurrent.futures)
- Already using Playwright; no new deps

### Ollama Parallelization
- Ollama daemon listening on localhost:11434
- Enough memory for 4–5 concurrent model inference (~1GB each)

### Rate Limiting Backoff
- Standard library only (time, requests)

---

## Risk Assessment

| Optimization | Risk Level | Mitigation |
|--------------|-----------|-----------|
| Playwright batching | Low | Test with 5-shop batch first; monitor memory |
| Adaptive rate limiting | Low | Test against actual Google rate limits; fallback to fixed delays |
| GBP caching | Low | Add TTL; verify cache misses on stale data |
| Yelp fallback | Medium | Web scraping less reliable; keep API fallback |
| Ollama parallelization | Low | Ollama handles threading; test with load |
| Feedback analysis parallelization | Low | Thread-safe Ollama calls; verify output consistency |
| Batch size increase | Medium | Depends on call system; test with simulator first |

---

## Success Metrics

After implementing all optimizations:

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Phase 1/2 runtime (50 shops) | 3–5 min | 1–2 min | <2 min |
| Phase 3 iteration time | 10–15 min | 2–3 min | <3 min |
| Script generation time | 6 sec | 1.5 sec | <2 sec |
| Feedback analysis time | 6–9 sec | 2–3 sec | <3 sec |
| Ollama API calls/iteration | N/A | 50% reduction | <5 calls |
| Manual scoring overhead | Hours | Minutes | <5 min |
| Intern operational readiness | Medium | High | Easy |

---

## Rollout Plan

### Week 1 (This Sprint)
- ✅ Implement Numverify heuristic (done)
- ✅ Document efficiency audit (this document)
- 🔄 Add script caching logic (1 hour)

### Week 2–3 (Next Sprint)
- Implement Playwright batching (4 hours)
- Implement parallel Ollama generation (2 hours)
- Implement parallel feedback analysis (1 hour)
- Increase batch size to 20 shops (30 min)
- Integrate adaptive rate limiting (1 hour)
- **Total**: 8.5 hours

### Month 2 (Q1 2025)
- GBP caching (1 hour)
- Yelp web scraping fallback (2 hours)
- Advanced analytics (batch forecasting, cohort analysis)
- **Total**: 3+ hours

---

## Conclusion

The agentic priming stack is well-architected for efficiency gains. Sequential operations (Playwright waits, Ollama inference) are the primary bottleneck, solvable with parallelization. Implementing the high-priority optimizations (Playwright batching, parallel Ollama, script caching) will deliver **60–80% runtime reduction** across both phases, enabling faster iteration and better intern operability.

**Recommended immediate action**: Implement script caching logic (1 hour, this sprint) to unblock Phase 3 workflow smoothness while planning next sprint's parallelization work.
