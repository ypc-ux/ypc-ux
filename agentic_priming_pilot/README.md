# Agentic Priming — Local Pilot (Decatur/30035 Auto Body & Tire)

Phase 1 + Phase 2 pipeline: find independent auto body/tire shops within 5 miles
of 30035, pull phone numbers from up to 3 sources, normalize + cross-verify them,
and output a CSV with a `confidence` column.

Phase 3 (Agentic Priming scoring + outcome logging) is a separate system —
this pilot only produces the verified call list it needs as input.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
```

Required env vars (see `.env.example`):

- `GOOGLE_PLACES_API_KEY` — required. Text Search + Place Details.
- `YELP_API_KEY` — optional. Third-source cross-check. Skipped (source left blank)
  if not set.
- `NUMVERIFY_API_KEY` — optional. Carrier-type lookup for the mobile-number
  rejection heuristic. Without it, rejection is skipped and everything else
  still runs (rows just won't get auto-rejected for being a mobile number).

## Run

```bash
python pipeline.py --zip 30035 --radius-miles 5 --out shops.csv
```

Add `--limit N` while testing to cap API calls, and `--verbose` for progress
logging.

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

## Phase 3 — score, call, compare (`phase3/`)

Harness for the outcome-feedback loop: register script variants, capture a
baseline score for each *before* calling anyone, log real outcomes, then
compare score against conversion.

**The 87-heuristic scorer is not implemented here, on purpose.** The pilot's
whole claim is "the score predicted what converted" — a locally invented
scorer would produce authoritative-looking numbers that quietly destroy that
claim. `phase3/scorer.py` is an adapter with two honest backends:

- `manual` (default) — you run the script through the real scorer yourself and
  type the numbers in. Real values, slower.
- `http` — calls a real scoring endpoint. Set `AGENTIC_PRIMING_API_URL` (and
  optionally `AGENTIC_PRIMING_API_KEY`). The response mapping in
  `_from_http_payload()` is a best guess at the payload shape; adjust it once
  the real contract is known. It raises rather than defaulting on a mismatch,
  so a bad contract fails loudly instead of silently scoring 0.

There is deliberately no "estimate" backend.

```bash
# 1. register both script versions (phone and in-person score separately)
python -m phase3.cli add-script --name opener-a --context phone --file opener.txt
python -m phase3.cli add-script --name walkup-a --context in_person --file walkup.txt

# 2. baseline BEFORE any calls
python -m phase3.cli score 1 --backend manual --total 72 --humanity pass \
    --gate-flags '{"pressure": false}'

# 3. log each real attempt
python -m phase3.cli log-outcome 1 --business "Ray's Body Shop" \
    --phone +14045551212 --outcome booked --targets shops.csv

# 4. compare once you have ~15-20 attempts
python -m phase3.cli report
```

Outcomes are `booked | no_answer | declined | hung_up`. Passing `--targets`
warns if the number you're logging wasn't a `verified` row from Phase 2.

State lives in `pilot.db` (SQLite) — inspectable with `sqlite3 pilot.db`.

The report prints Wilson 95% confidence intervals alongside every rate and
flags when intervals overlap too much to support a claim. At 15-20 attempts
they will overlap a lot; that caveat is there so the case study doesn't
overstate a 2-point gap as a proven result.
