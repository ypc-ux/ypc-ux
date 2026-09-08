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
