#!/usr/bin/env python3
"""
Agentic Priming local pilot — Phase 1 (find) + Phase 2 (triple-verify).

Finds independent auto body / collision / tire shops within a radius of a
zip code via web scraping (Google Search + Google Maps), cross-checks phone
numbers against the business's own website and (optionally) Yelp, normalizes
everything to E.164, and scores a confidence tier per the spec:

    verified       -> number agrees identically across >=2 of 3 sources
    check_manually -> only 1 source, or sources disagree
    rejected       -> looks like a mobile number and isn't the GBP number

No API keys required. YELP_API_KEY and NUMVERIFY_API_KEY are optional —
features they gate are skipped cleanly when absent.
"""
import argparse
import csv
import difflib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote, urljoin

import phonenumbers
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from franchises import is_franchise

load_dotenv()

log = logging.getLogger("pilot")

YELP_KEY = os.environ.get("YELP_API_KEY", "")
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_API_KEY", "")

SEARCH_QUERIES = [
    ("auto body shop", "body_shop"),
    ("collision repair center", "body_shop"),
    ("tire shop", "tire_shop"),
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

PHONE_PATTERN = re.compile(
    r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
)


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
    """Geocode zip code to lat/lng using Nominatim (OpenStreetMap)."""
    resp = SESSION.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": zip_code, "format": "json", "limit": 1},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise RuntimeError(f"Could not geocode zip {zip_code}")
    return float(data[0]["lat"]), float(data[0]["lon"])


def scrape_google_search(query: str, limit: int = 20) -> list:
    """Scrape Google Search for Business Profile results. Returns list of dicts
    with 'name', 'address', and 'maps_url' keys."""
    results = []
    search_query = f'"{query}" near 30035'
    url = f"https://www.google.com/search?q={quote(search_query)}"

    try:
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Google Search scrape failed: %s", exc)
        return results

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract Business Profile cards from search results
    for card in soup.find_all("div", attrs={"data-lpage": True})[:limit]:
        try:
            name_elem = card.find("h3")
            if not name_elem:
                continue
            name = name_elem.get_text(strip=True)

            # Find Maps link
            maps_link = None
            for link in card.find_all("a"):
                href = link.get("href", "")
                if "maps.google.com" in href or "google.com/maps" in href:
                    maps_link = href
                    break

            if maps_link and name:
                results.append({"name": name, "maps_url": maps_link})
        except Exception as e:
            log.debug("Error parsing card: %s", e)
            continue

    return results


def scrape_google_maps(query: str, lat: float, lng: float, limit: int = 20) -> list:
    """Scrape Google Maps for businesses. Returns list of dicts with
    'name', 'address', and 'maps_url' keys."""
    results = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to Maps with search
            search_url = f"https://www.google.com/maps/search/{quote(query)}"
            page.goto(search_url, wait_until="networkidle")

            # Wait for results to load
            time.sleep(2)

            # Extract business cards from sidebar
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            for result_elem in soup.find_all("div", attrs={"role": "button"})[:limit]:
                try:
                    name = result_elem.get_text(strip=True)
                    if not name or len(name) < 2:
                        continue

                    # Try to get Maps link
                    link_elem = result_elem.find("a")
                    maps_url = link_elem.get("href", "") if link_elem else ""

                    if name and (maps_url or not results):
                        results.append({"name": name, "maps_url": maps_url})
                except Exception as e:
                    log.debug("Error parsing Maps result: %s", e)
                    continue

            browser.close()
    except Exception as e:
        log.warning("Google Maps scrape failed: %s", e)

    return results


def gbp_scrape_details(maps_url: str) -> dict:
    """Scrape Google Business Profile page for details. Returns dict with
    'name', 'address', 'phone_gbp', 'rating', 'review_count', 'website', 'maps_url'."""
    details = {"name": "", "address": "", "phone_gbp": "", "rating": "",
               "review_count": "", "website": "", "maps_url": maps_url}

    if not maps_url:
        return details

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(maps_url, wait_until="networkidle", timeout=30000)
            time.sleep(1)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Try to extract JSON-LD structured data
            for script in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script.string)
                    if data.get("@type") == "LocalBusiness" or data.get("@type") == "Organization":
                        details["name"] = data.get("name", details["name"])
                        details["address"] = data.get("address", {}).get("streetAddress", "") if isinstance(data.get("address"), dict) else ""
                        details["phone_gbp"] = data.get("telephone", details["phone_gbp"])
                        details["rating"] = str(data.get("aggregateRating", {}).get("ratingValue", "")) if data.get("aggregateRating") else ""
                        details["review_count"] = str(data.get("aggregateRating", {}).get("reviewCount", "")) if data.get("aggregateRating") else ""
                        details["website"] = data.get("url", details["website"])
                        break
                except json.JSONDecodeError:
                    continue

            # Fallback: extract from page text if JSON-LD didn't work
            if not details["name"]:
                h1 = soup.find("h1")
                if h1:
                    details["name"] = h1.get_text(strip=True)

            # Extract phone number from page text
            if not details["phone_gbp"]:
                text = soup.get_text()
                match = PHONE_PATTERN.search(text)
                if match:
                    details["phone_gbp"] = match.group(0)

            # Extract website link
            if not details["website"]:
                for link in soup.find_all("a"):
                    href = link.get("href", "")
                    if "http" in href and "google" not in href and "maps" not in href:
                        details["website"] = href
                        break

            browser.close()
    except Exception as e:
        log.debug("GBP scrape failed for %s: %s", maps_url, e)

    return details


def extract_zip(address_components: list) -> str:
    for comp in address_components or []:
        if "postal_code" in comp.get("types", []):
            return comp.get("long_name", "")
    return ""


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
    log.info("Geocoding %s ...", zip_code)
    try:
        lat, lng = geocode_zip(zip_code)
    except Exception as e:
        sys.exit(f"Failed to geocode {zip_code}: {e}")

    all_candidates = []

    # Step 1: Scrape Google Search results
    for query, category in SEARCH_QUERIES:
        log.info("Scraping Google Search for %r ...", query)
        search_results = scrape_google_search(query, limit=20)
        for result in search_results:
            result["category"] = category
            all_candidates.append(result)

    log.info("Got %d candidates from Google Search", len(all_candidates))

    # Step 2: Fallback to Google Maps scraping if needed
    if len(all_candidates) < 5:
        for query, category in SEARCH_QUERIES:
            log.info("Fallback: Scraping Google Maps for %r ...", query)
            maps_results = scrape_google_maps(query, lat, lng, limit=10)
            for result in maps_results:
                # Dedupe against existing
                is_dup = any(
                    difflib.SequenceMatcher(
                        None,
                        result.get("name", "").lower(),
                        c.get("name", "").lower()
                    ).ratio() > 0.8
                    for c in all_candidates
                )
                if not is_dup:
                    result["category"] = category
                    all_candidates.append(result)

    log.info("Found %d total candidates", len(all_candidates))

    shops = []
    to_process = all_candidates[:limit] if limit else all_candidates

    for candidate in to_process:
        maps_url = candidate.get("maps_url", "")
        if not maps_url:
            log.debug("Skipping candidate with no maps_url: %s", candidate.get("name"))
            continue

        log.info("Scraping details for %s ...", candidate.get("name"))
        details = gbp_scrape_details(maps_url)
        if not details.get("name"):
            log.debug("Failed to extract details from %s", maps_url)
            continue

        name = details.get("name", "")
        if is_franchise(name):
            log.info("Excluding franchise: %s", name)
            continue

        shop = Shop(
            business_name=name,
            category=candidate.get("category", ""),
            address=details.get("address", ""),
            zip="",
            phone_gbp=normalize_phone(details.get("phone_gbp", "")),
            website_url=details.get("website", ""),
            google_rating=details.get("rating", ""),
            review_count=details.get("review_count", ""),
            maps_url=maps_url,
        )

        log.info("Checking website for %s ...", shop.business_name)
        shop.phone_website = scrape_website_phone(shop.website_url)

        log.info("Cross-checking Yelp for %s ...", shop.business_name)
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

        # Rate limiting
        time.sleep(1)

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
