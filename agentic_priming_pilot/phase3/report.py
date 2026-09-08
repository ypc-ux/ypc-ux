"""Score-vs-outcome comparison — the actual proof artifact for the pilot.

The claim this is meant to support is "the tool's score predicted what worked
in the field." That claim is only as good as the sample behind it, so every
rate here is reported with its denominator and a Wilson confidence interval.
At pilot volumes (15-20 attempts) those intervals are wide, and this module
says so rather than letting a 2-point gap read as a result.
"""
import math

from . import store


def wilson_interval(successes: int, n: int, z: float = 1.96):
    """95% Wilson score interval. Behaves sanely at small n and at 0%/100%,
    where the normal approximation does not."""
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z**2 / n
    center = (phat + z**2 / (2 * n)) / denom
    margin = (
        z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    ) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def summarize_script(conn, script_row):
    attempts = store.attempts_for(conn, script_row["id"])
    baseline = store.latest_baseline(conn, script_row["id"])

    total = len(attempts)
    reached = [a for a in attempts if a["outcome"] != "no_answer"]
    booked = [a for a in attempts if a["outcome"] == "booked"]

    booked_lo, booked_hi = wilson_interval(len(booked), total)

    return {
        "script_id": script_row["id"],
        "name": script_row["name"],
        "context": script_row["context"],
        "score": baseline["total_score"] if baseline else None,
        "humanity_check": (
            bool(baseline["humanity_check"]) if baseline else None
        ),
        "scorer_backend": baseline["scorer_backend"] if baseline else None,
        "attempts": total,
        "reached": len(reached),
        "booked": len(booked),
        "book_rate": (len(booked) / total) if total else None,
        "book_rate_ci": (booked_lo, booked_hi) if total else None,
    }


def build_report(conn):
    return [summarize_script(conn, row) for row in store.list_scripts(conn)]


def _fmt_pct(value):
    return "—" if value is None else f"{value * 100:.0f}%"


def render(rows) -> str:
    if not rows:
        return "No script versions recorded yet. Add one with `add-script`."

    lines = []
    header = (
        f"{'id':>3}  {'script':<24} {'context':<10} {'score':>7} "
        f"{'hum':>4} {'att':>4} {'book':>5} {'rate':>6}  95% CI"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for r in rows:
        score = "—" if r["score"] is None else f"{r['score']:.1f}"
        hum = "—" if r["humanity_check"] is None else (
            "pass" if r["humanity_check"] else "FAIL"
        )
        if r["book_rate_ci"]:
            lo, hi = r["book_rate_ci"]
            ci = f"[{_fmt_pct(lo)}, {_fmt_pct(hi)}]"
        else:
            ci = "—"
        lines.append(
            f"{r['script_id']:>3}  {r['name'][:24]:<24} {r['context']:<10} "
            f"{score:>7} {hum:>4} {r['attempts']:>4} {r['booked']:>5} "
            f"{_fmt_pct(r['book_rate']):>6}  {ci}"
        )

    scored = [r for r in rows if r["score"] is not None and r["attempts"] > 0]
    total_attempts = sum(r["attempts"] for r in rows)

    lines.append("")
    if len(scored) < 2:
        lines.append(
            "Not enough scored-and-called variants yet to compare score "
            "against conversion. Need at least 2."
        )
        return "\n".join(lines)

    best_score = max(scored, key=lambda r: r["score"])
    best_rate = max(scored, key=lambda r: r["book_rate"])
    agree = best_score["script_id"] == best_rate["script_id"]

    lines.append(
        f"Highest-scoring variant: {best_score['name']} "
        f"(score {best_score['score']:.1f}, booked {_fmt_pct(best_score['book_rate'])})"
    )
    lines.append(
        f"Highest-converting variant: {best_rate['name']} "
        f"(score {best_rate['score']:.1f}, booked {_fmt_pct(best_rate['book_rate'])})"
    )
    lines.append(
        "Score and field outcome AGREE on the top variant."
        if agree
        else "Score and field outcome DISAGREE on the top variant."
    )

    if total_attempts < 30 or any(
        r["book_rate_ci"] and (r["book_rate_ci"][1] - r["book_rate_ci"][0]) > 0.3
        for r in scored
    ):
        lines.append("")
        lines.append(
            "CAVEAT: confidence intervals overlap heavily at this sample size "
            f"(n={total_attempts} attempts). Treat the agree/disagree line as "
            "directional only — it is not yet evidence that the score predicts "
            "conversion, and should not be presented to other operators as if "
            "it were."
        )

    return "\n".join(lines)
