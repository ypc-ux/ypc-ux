#!/usr/bin/env python3
"""
Agentic Priming local pilot — Phase 1 (find) + Phase 2 (triple-verify).

Finds independent auto body / collision / tire shops within a radius of a
zip code via Google Places, cross-checks phone numbers against the
business's own website and (optionally) Yelp Fusion, normalizes everything
to E.164, and scores a confidence tier per the spec:

    verified       -> number agrees identically across >=2 of 3 sources
    check_manually -> only 1 source, or sources disagree
    rejected       -> looks like a mobile number and isn't the GBP number

Requires GOOGLE_PLACES_API_KEY. YELP_API_KEY and NUMVERIFY_API_KEY are
optional — features they gate are skipped cleanly when absent.
"""
import argparse
import csv
import difflib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import phonenumbers
import requests
from dotenv import load_dotenv

from franchises import is_franchise

load_dotenv()

log = logging.getLogger("pilot")

GOOGLE_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
YELP_KEY = os.environ.get("YELP_API_KEY", "")
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_API_KEY", "")

SEARCH_QUERIES = [
    ("auto body shop", "body_shop"),
    ("collision repair center", "body_shop"),
    ("tire shop", "tire_shop"),
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "agentic-priming-pilot/1.0"})


@dataclass
class Shop:
    business_name: str
    category: str
    address: str = ""
    zip: str = ""
    lat: float = 0.0
    lng: float = 0.0
    place_id: str = ""
    phone_gbp: str = ""
    phone_website: str = ""
    phone_third_source: str = ""
    website_url: str = ""
    google_rating: str = ""
    review_count: str = ""
    maps_url: str = ""
    notes: list = field(default_factory=list)
    confidence: str = ""


def normalize_phone(raw: Optional[str]) -> str:
    """Best-effort normalize to E.164 (+1XXXXXXXXXX). Returns '' if unparseable."""
    if not raw:
        return ""
    try:
        parsed = phonenumbers.parse(raw, "US")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except phonenumbers.NumberParseException:
        pass
    return ""


def geocode_zip(zip_code: str) -> tuple:
    resp = SESSION.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": zip_code, "key": GOOGLE_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        raise RuntimeError(f"Could not geocode zip {zip_code}: {data.get('status')}")
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def places_text_search(query: str, lat: float, lng: float, radius_m: int) -> list:
    results = []
    params = {
        "query": query,
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "key": GOOGLE_KEY,
    }
    while True:
        resp = SESSION.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            log.warning("Places text search error: %s", data.get("status"))
            break
        results.extend(data.get("results", []))
        next_token = data.get("next_page_token")
        if not next_token:
            break
        # Google requires a short delay before the token becomes valid.
        time.sleep(2)
        params = {"pagetoken": next_token, "key": GOOGLE_KEY}
    return results


def place_details(place_id: str) -> dict:
    resp = SESSION.get(
        "https://maps.googleapis.com/maps/api/place/details/json",
        params={
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,"
            "international_phone_number,website,business_status,"
            "rating,user_ratings_total,url,address_component",
            "key": GOOGLE_KEY,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        log.warning("Place details error for %s: %s", place_id, data.get("status"))
        return {}
    return data.get("result", {})


def extract_zip(address_components: list) -> str:
    for comp in address_components or []:
        if "postal_code" in comp.get("types", []):
            return comp.get("long_name", "")
    return ""


PHONE_PATTERN = re.compile(
    r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
)


def scrape_website_phone(url: str) -> str:
    """Fetch the site's homepage and a likely contact page, look for a phone
    number in the raw HTML. Best-effort — many sites will fail this."""
    if not url:
        return ""
    candidates = [url]
    for path in ("/contact", "/contact-us", "/contact-us/", "/about", "/about-us"):
        candidates.append(url.rstrip("/") + path)

    for candidate in candidates:
        try:
            resp = SESSION.get(candidate, timeout=10, allow_redirects=True)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        match = PHONE_PATTERN.search(resp.text)
        if match:
            normalized = normalize_phone(match.group(0))
            if normalized:
                return normalized
    return ""


def yelp_lookup(name: str, address: str, zip_code: str) -> str:
    if not YELP_KEY:
        return ""
    try:
        resp = SESSION.get(
            "https://api.yelp.com/v3/businesses/search",
            headers={"Authorization": f"Bearer {YELP_KEY}"},
            params={"term": name, "location": f"{address}, {zip_code}", "limit": 3},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning("Yelp lookup failed for %s: %s", name, exc)
        return ""

    best_match, best_score = None, 0.0
    for biz in data.get("businesses", []):
        score = difflib.SequenceMatcher(
            None, name.lower(), biz.get("name", "").lower()
        ).ratio()
        if score > best_score:
            best_score, best_match = score, biz
    if best_match and best_score >= 0.6:
        return normalize_phone(best_match.get("phone", ""))
    return ""


def numverify_is_mobile(e164_number: str) -> Optional[bool]:
    """Returns True if carrier lookup says mobile, False if landline/other,
    None if lookup unavailable or inconclusive."""
    if not NUMVERIFY_KEY or not e164_number:
        return None
    try:
        resp = SESSION.get(
            "http://apilayer.net/api/validate",
            params={
                "access_key": NUMVERIFY_KEY,
                "number": e164_number,
                "country_code": "US",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning("NumVerify lookup failed for %s: %s", e164_number, exc)
        return None
    line_type = (data.get("line_type") or "").lower()
    if not line_type:
        return None
    return line_type == "mobile"


def fuzzy_key(name: str, address: str) -> str:
    """Loose normalized key for dedupe: lowercase, strip punctuation/whitespace,
    drop common suffixes."""
    combined = f"{name} {address}".lower()
    combined = re.sub(r"[^a-z0-9 ]", "", combined)
    combined = re.sub(r"\s+", " ", combined).strip()
    return combined


def dedupe(shops: list) -> list:
    kept = []
    kept_keys = []
    for shop in shops:
        key = fuzzy_key(shop.business_name, shop.address)
        is_dupe = False
        for existing_key in kept_keys:
            if difflib.SequenceMatcher(None, key, existing_key).ratio() >= 0.85:
                is_dupe = True
                break
        if not is_dupe:
            kept.append(shop)
            kept_keys.append(key)
    return kept


def score_confidence(shop: Shop) -> None:
    numbers = {
        "gbp": shop.phone_gbp,
        "website": shop.phone_website,
        "third": shop.phone_third_source,
    }
    present = {k: v for k, v in numbers.items() if v}

    if not present:
        shop.confidence = "check_manually"
        shop.notes.append("No phone number found from any source.")
        return

    # Rejection heuristic: a present number tests as mobile AND it is not
    # the number listed on the GBP.
    for source_name, number in present.items():
        if source_name == "gbp":
            continue
        is_mobile = numverify_is_mobile(number)
        if is_mobile and number != shop.phone_gbp:
            shop.confidence = "rejected"
            shop.notes.append(
                f"{source_name} phone {number} flagged as mobile and does not "
                "match GBP number — likely a personal cell, not the shop line."
            )
            return

    # Agreement across >=2 of 3 sources.
    from collections import Counter

    counts = Counter(present.values())
    top_number, top_count = counts.most_common(1)[0]
    if top_count >= 2:
        shop.confidence = "verified"
        shop.notes.append(
            f"Number {top_number} confirmed across {top_count} source(s): "
            f"{', '.join(s for s, n in present.items() if n == top_number)}."
        )
    else:
        shop.confidence = "check_manually"
        if len(present) == 1:
            shop.notes.append(
                f"Only one source has a number ({next(iter(present))})."
            )
        else:
            shop.notes.append("Sources disagree on the phone number.")


def run(zip_code: str, radius_miles: float, limit: Optional[int], out_path: str) -> None:
    if not GOOGLE_KEY:
        sys.exit("GOOGLE_PLACES_API_KEY is not set. Copy .env.example to .env and fill it in.")

    radius_m = int(radius_miles * 1609.34)
    log.info("Geocoding %s ...", zip_code)
    lat, lng = geocode_zip(zip_code)

    raw_results = {}
    for query, category in SEARCH_QUERIES:
        log.info("Searching Places for %r ...", query)
        for result in places_text_search(query, lat, lng, radius_m):
            place_id = result.get("place_id")
            if not place_id:
                continue
            existing = raw_results.get(place_id)
            if existing:
                # Same place found by multiple queries -> mark "both" if it
                # was tire+body.
                if existing[1] != category:
                    raw_results[place_id] = (result, "both")
            else:
                raw_results[place_id] = (result, category)

    log.info("Found %d unique Places candidates before filtering.", len(raw_results))

    shops = []
    place_ids = list(raw_results.keys())
    if limit:
        place_ids = place_ids[:limit]

    for place_id in place_ids:
        _, category = raw_results[place_id]
        details = place_details(place_id)
        if not details:
            continue
        name = details.get("name", "")
        if is_franchise(name):
            log.info("Excluding franchise: %s", name)
            continue
        if details.get("business_status") not in (None, "OPERATIONAL"):
            log.info("Skipping non-operational business: %s", name)
            continue

        shop = Shop(
            business_name=name,
            category=category,
            address=details.get("formatted_address", ""),
            zip=extract_zip(details.get("address_component", [])),
            place_id=place_id,
            phone_gbp=normalize_phone(
                details.get("international_phone_number")
                or details.get("formatted_phone_number")
            ),
            website_url=details.get("website", ""),
            google_rating=str(details.get("rating", "")),
            review_count=str(details.get("user_ratings_total", "")),
            maps_url=details.get("url", ""),
        )

        log.info("Checking website for %s ...", shop.business_name)
        shop.phone_website = scrape_website_phone(shop.website_url)

        log.info("Cross-checking third source for %s ...", shop.business_name)
        shop.phone_third_source = yelp_lookup(
            shop.business_name, shop.address, shop.zip
        )
        if not YELP_KEY:
            shop.notes.append(
                "No third-source lookup configured (set YELP_API_KEY) — "
                "cross-check BBB or Georgia SOS manually before calling."
            )

        score_confidence(shop)
        shops.append(shop)

    shops = dedupe(shops)
    log.info("Writing %d rows to %s", len(shops), out_path)

    fieldnames = [
        "business_name",
        "category",
        "address",
        "zip",
        "phone_gbp",
        "phone_website",
        "phone_third_source",
        "website_url",
        "google_rating",
        "review_count",
        "maps_url",
        "confidence",
        "notes",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for shop in shops:
            row = shop.__dict__.copy()
            row["notes"] = " | ".join(shop.notes)
            writer.writerow({k: row[k] for k in fieldnames})

    verified = sum(1 for s in shops if s.confidence == "verified")
    check = sum(1 for s in shops if s.confidence == "check_manually")
    rejected = sum(1 for s in shops if s.confidence == "rejected")
    log.info(
        "Done. verified=%d check_manually=%d rejected=%d total=%d",
        verified,
        check,
        rejected,
        len(shops),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", default="30035")
    parser.add_argument("--radius-miles", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=None, help="Cap number of places processed (for testing).")
    parser.add_argument("--out", default="shops.csv")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run(args.zip, args.radius_miles, args.limit, args.out)


if __name__ == "__main__":
    main()
