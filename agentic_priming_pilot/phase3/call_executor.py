"""Call execution module for Phase 3 automated workflow.

MVP: Simulates calls with configurable outcomes for testing.
Future: Integrate with real dialer (Twilio, etc.).
"""
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)


def call_shop_async(
    shop: dict,
    script_id: int,
    script_body: str,
    channel: str = "phone",
    simulate: bool = True,
) -> dict:
    """Execute a call to a shop using a script variant.

    Args:
        shop: Dict from shops.csv with keys: business_name, phone_gbp, etc.
        script_id: Which script version to use
        script_body: The actual script text
        channel: "phone" or "walk_in"
        simulate: If True, simulate outcome; else attempt real call (not yet implemented)

    Returns:
        Dict with keys: script_id, business_name, phone, outcome, channel, notes
    """
    phone = shop.get("phone_gbp") or shop.get("phone_website") or ""

    if not phone:
        return {
            "script_id": script_id,
            "business_name": shop.get("business_name", "Unknown"),
            "phone": "",
            "outcome": "wrong_number",
            "channel": channel,
            "notes": "No phone number in shop record",
        }

    if simulate:
        return simulate_call(shop, script_body, script_id, channel)
    else:
        logger.warning("Real call execution not yet implemented")
        return simulate_call(shop, script_body, script_id, channel)


def simulate_call(
    shop: dict,
    script: str,
    script_id: int,
    channel: str = "phone",
) -> dict:
    """Simulate a call outcome for testing/MVP.

    Outcomes are probabilistic but influenced by script quality and business type.
    Purpose: Test full Deerflow workflow without making real calls.

    Args:
        shop: Business record
        script: Script text
        script_id: Script variant ID
        channel: "phone" or "walk_in"

    Returns:
        Call outcome dict
    """
    phone = shop.get("phone_gbp") or shop.get("phone_website") or ""
    business_name = shop.get("business_name", "Unknown")

    outcomes = ["booked", "declined", "no_answer", "hung_up"]
    probabilities = [0.20, 0.35, 0.35, 0.10]

    script_quality_factor = _estimate_script_quality(script)
    probabilities[0] = min(0.35, probabilities[0] + (script_quality_factor * 0.15))
    probabilities[1] = max(0.10, probabilities[1] - (script_quality_factor * 0.10))

    outcome = random.choices(outcomes, weights=probabilities, k=1)[0]

    notes = _outcome_note(outcome, business_name, script_quality_factor)

    return {
        "script_id": script_id,
        "business_name": business_name,
        "phone": phone,
        "outcome": outcome,
        "channel": channel,
        "notes": notes,
    }


def _estimate_script_quality(script: str) -> float:
    """Heuristic estimate of script quality (0.0-1.0).

    Crude metrics: length, presence of call-to-action, personalization hints.
    """
    quality = 0.5

    if 100 < len(script) < 400:
        quality += 0.2

    ctas = ["?", "yes", "could", "think", "interested", "time"]
    if sum(1 for cta in ctas if cta.lower() in script.lower()) >= 2:
        quality += 0.15

    if any(word in script.lower() for word in ["you", "your", "business"]):
        quality += 0.15

    return min(1.0, max(0.0, quality))


def _outcome_note(outcome: str, business_name: str, quality: float) -> str:
    """Generate a realistic-sounding note for simulated call."""
    notes_by_outcome = {
        "booked": [
            f"Owner interested. Scheduled consultation for next Tuesday.",
            f"Quick decision maker. Wants pricing ASAP.",
            f"Already mentioned our service to other shop. Immediate need.",
        ],
        "declined": [
            f"'Don't need service right now'",
            f"Too busy to talk; not interested.",
            f"'Already have a vendor we use'",
        ],
        "no_answer": [
            f"Voicemail full",
            f"Voicemail not set up",
            f"Line went to menu, transferred to voicemail",
        ],
        "hung_up": [
            f"Ended call after 20 seconds",
            f"'Not interested' and hung up",
            f"Got transferred, line dropped",
        ],
    }

    note = random.choice(notes_by_outcome.get(outcome, [outcome]))
    return note


def batch_call_shops(
    shops: list,
    script_id: int,
    script_body: str,
    batch_size: int = 10,
    channel: str = "phone",
) -> list:
    """Execute batch of calls to multiple shops.

    Args:
        shops: List of shop dicts
        script_id: Which script to use for all
        script_body: Script content
        batch_size: How many to call (default 10)
        channel: "phone" or "walk_in"

    Returns:
        List of call outcome dicts
    """
    results = []
    for shop in shops[:batch_size]:
        try:
            result = call_shop_async(shop, script_id, script_body, channel)
            results.append(result)
            logger.info(
                f"Call to {shop.get('business_name')}: {result['outcome']}"
            )
        except Exception as e:
            logger.error(f"Error calling {shop.get('business_name')}: {e}")
            results.append({
                "script_id": script_id,
                "business_name": shop.get("business_name", "Unknown"),
                "phone": shop.get("phone_gbp", ""),
                "outcome": "no_answer",
                "channel": channel,
                "notes": f"Execution error: {str(e)[:100]}",
            })

    logger.info(f"Batch complete: {len(results)}/{batch_size} calls executed")
    return results
