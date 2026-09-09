"""Phase 3 Ollama integration: orchestration layer for automated workflow.

Deerflow calls these functions to drive the fully automated loop:
generate scripts → score baselines → batch call → log outcomes → analyze → regenerate.
"""
import csv
import logging
import sys
from pathlib import Path
from typing import Optional

from . import store

try:
    from .. import ollama_script_gen
except ImportError:
    import ollama_script_gen

logger = logging.getLogger(__name__)


def load_shops_csv(csv_path: str) -> list:
    """Load verified shops from Phase 2 output CSV.

    Args:
        csv_path: Path to shops.csv from Phase 1/2

    Returns:
        List of dicts with keys: business_name, address, phone_gbp, confidence, etc.
    """
    shops = []
    try:
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("confidence") == "verified":
                    shops.append(row)
        logger.info(f"Loaded {len(shops)} verified shops from {csv_path}")
    except Exception as e:
        logger.error(f"Error loading shops: {e}")

    return shops


def generate_and_register_scripts(
    conn: "sqlite3.Connection",
    context: str,
    num_variants: int = 2,
    script_context: str = "phone",
    feedback: Optional[list] = None,
    ollama_model: str = "mistral",
) -> list:
    """Generate new scripts with Ollama and register them in Phase 3 DB.

    Args:
        conn: SQLite connection to pilot.db
        context: Target customer context (e.g., "auto body shop owner in Atlanta")
        num_variants: Number of script variants to generate
        script_context: "phone" or "in_person"
        feedback: Optional feedback list for adaptive generation
        ollama_model: Which model to use (default: mistral)

    Returns:
        List of dicts with: script_id, name, variant_num, context
    """
    try:
        variants = ollama_script_gen.generate_scripts(
            context=context,
            num_variants=num_variants,
            feedback=feedback,
            model=ollama_model,
        )
    except Exception as e:
        logger.error(f"Failed to generate scripts: {e}")
        return []

    registered = []
    for variant in variants:
        try:
            script_name = f"ollama-{script_context}-v{variant['variant_num']}"
            script_id = store.add_script(
                conn,
                name=script_name,
                context=script_context,
                body=variant["body"],
            )
            registered.append({
                "script_id": script_id,
                "name": script_name,
                "variant_num": variant["variant_num"],
                "context": script_context,
                "body": variant["body"],
            })
            logger.info(f"Registered script {script_id}: {script_name}")
        except Exception as e:
            logger.warning(f"Could not register variant {variant['variant_num']}: {e}")

    return registered


def score_all_variants(
    conn: "sqlite3.Connection",
    backend: str = "manual",
    api_url: Optional[str] = None,
) -> dict:
    """Score all unscored script variants.

    For MVP, this is a placeholder that reminds user to score manually.
    Real implementation would integrate with actual scoring service.

    Args:
        conn: SQLite connection
        backend: "manual" (user provides score) or "http" (call external scorer)
        api_url: Scoring endpoint (for http backend)

    Returns:
        Dict with: scored_count, needs_manual_count, scorer_backend
    """
    unscored = []
    for script in store.list_scripts(conn):
        baseline = store.latest_baseline(conn, script["id"])
        if not baseline:
            unscored.append(script)

    logger.info(f"Found {len(unscored)} unscored scripts")

    if backend == "manual" and unscored:
        logger.warning(
            f"Manual scoring required for {len(unscored)} scripts. "
            "Run: python -m phase3.cli score <id> --backend manual --total <score> --humanity pass"
        )

    return {
        "scored_count": len(store.list_scripts(conn)) - len(unscored),
        "needs_manual_count": len(unscored),
        "scorer_backend": backend,
    }


def log_outcomes_bulk(
    conn: "sqlite3.Connection",
    outcomes: list,
) -> dict:
    """Bulk-log call outcomes from batch execution.

    Args:
        conn: SQLite connection
        outcomes: List of dicts with keys:
                  script_id, business_name, phone, outcome, channel, notes

    Returns:
        Dict with: recorded_count, failed_count
    """
    recorded = 0
    failed = 0

    for outcome in outcomes:
        try:
            store.record_attempt(
                conn,
                script_version_id=outcome.get("script_id"),
                business_name=outcome.get("business_name", ""),
                phone=outcome.get("phone", ""),
                channel=outcome.get("channel", "phone"),
                outcome=outcome.get("outcome", "no_answer"),
                notes=outcome.get("notes", ""),
            )
            recorded += 1
        except Exception as e:
            logger.warning(f"Failed to log outcome for {outcome.get('business_name')}: {e}")
            failed += 1

    logger.info(f"Logged {recorded} outcomes ({failed} failures)")
    return {"recorded_count": recorded, "failed_count": failed}


def analyze_recent_attempts(
    conn: "sqlite3.Connection",
    limit: int = 20,
) -> dict:
    """Analyze recent call attempts to extract feedback patterns.

    Args:
        conn: SQLite connection
        limit: How many recent attempts to analyze

    Returns:
        Dict from ollama_script_gen.analyze_booking_feedback()
    """
    all_attempts = conn.execute(
        "SELECT * FROM attempts ORDER BY contacted_at DESC LIMIT ?",
        (limit,),
    ).fetchall()

    attempts_list = [dict(row) for row in all_attempts]

    feedback = ollama_script_gen.analyze_booking_feedback(attempts_list)
    logger.info(
        f"Analyzed {len(attempts_list)} attempts: "
        f"{feedback['booked_count']} booked, {feedback['declined_count']} declined"
    )
    return feedback


def should_regenerate(
    feedback: dict,
    min_attempts: int = 10,
    min_booking_rate: float = 0.3,
) -> bool:
    """Heuristic: should we regenerate scripts based on feedback?

    Args:
        feedback: Dict from analyze_recent_attempts()
        min_attempts: Minimum attempts before considering regeneration
        min_booking_rate: If booking_rate below this, recommend regeneration

    Returns:
        True if regeneration recommended; False otherwise
    """
    total = feedback.get("booked_count", 0) + feedback.get("declined_count", 0)

    if total < min_attempts:
        logger.info(f"Only {total} attempts; not regenerating yet")
        return False

    if total == 0:
        return False

    booking_rate = feedback["booked_count"] / total
    if booking_rate < min_booking_rate:
        logger.warning(
            f"Booking rate {booking_rate:.1%} below target {min_booking_rate:.1%}; "
            "recommend regeneration"
        )
        return True

    logger.info(f"Booking rate {booking_rate:.1%} is acceptable")
    return False


def suggest_next_step(
    conn: "sqlite3.Connection",
    state: dict,
    total_attempts_limit: int = 50,
) -> str:
    """Suggest what Deerflow should do next based on current state.

    Args:
        conn: SQLite connection
        state: Dict with keys: iteration, total_attempts, scripts_generated, etc.
        total_attempts_limit: Stop after this many total attempts

    Returns:
        One of: "generate_variants", "score_variants", "call_shops",
                "analyze_feedback", "regenerate", "stop", "manual_review"
    """
    total_attempts = state.get("total_attempts", 0)
    scripts_generated = state.get("scripts_generated", 0)
    scripts_scored = state.get("scripts_scored", 0)

    if total_attempts >= total_attempts_limit:
        logger.info(f"Reached limit of {total_attempts_limit} attempts")
        return "stop"

    if scripts_generated == 0:
        return "generate_variants"

    if scripts_scored < scripts_generated:
        return "score_variants"

    if state.get("attempts_since_last_analysis", 0) >= 5:
        return "analyze_feedback"

    return "call_shops"


def attempt_iteration_summary(conn: "sqlite3.Connection") -> dict:
    """Get summary of current iteration state for workflow.

    Returns:
        Dict with: total_attempts, booked_count, declined_count, scripts_count, avg_booking_rate
    """
    attempts = conn.execute("SELECT * FROM attempts").fetchall()
    attempts_list = [dict(row) for row in attempts]

    booked = len([a for a in attempts_list if a.get("outcome") == "booked"])
    declined = len([a for a in attempts_list if a.get("outcome") == "declined"])
    total = len(attempts_list)

    scripts = conn.execute("SELECT COUNT(*) as cnt FROM script_versions").fetchone()
    scripts_count = scripts["cnt"] if scripts else 0

    booking_rate = (booked / total) if total > 0 else 0

    return {
        "total_attempts": total,
        "booked_count": booked,
        "declined_count": declined,
        "scripts_count": scripts_count,
        "avg_booking_rate": booking_rate,
    }
