"""Generate the pilot case study from real logged data.

Every number in the output is computed from `pilot.db` and the Phase 2 CSV.
Nothing here accepts a hand-typed figure, and the generator refuses to run on
an empty database rather than emitting a template full of placeholders that
could later be mistaken for results. The case study is an external-facing
sales artifact; a plausible-looking number in it that nobody actually measured
is the single worst failure mode this pilot has.
"""
import csv
from pathlib import Path

from . import report as report_mod
from . import store

MIN_ATTEMPTS_FOR_CLAIM = 30


class NotEnoughData(RuntimeError):
    pass


def phase2_counts(csv_path: Path) -> dict:
    """Confidence-tier breakdown from the Phase 2 output."""
    if not csv_path.exists():
        return {}
    counts = {"verified": 0, "check_manually": 0, "rejected": 0, "total": 0}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            counts["total"] += 1
            tier = row.get("confidence", "")
            if tier in counts:
                counts[tier] += 1
    return counts


def number_accuracy(conn) -> dict:
    """How often a number we called actually reached the intended business.

    no_answer is excluded from the denominator: it is evidence about
    availability, not about whether the number was correct.
    """
    rows = conn.execute("SELECT outcome FROM attempts WHERE phone != ''").fetchall()
    reached = sum(
        1 for r in rows if r["outcome"] in store.OUTCOMES_REACHED_BUSINESS
    )
    bad = sum(1 for r in rows if r["outcome"] in store.OUTCOMES_BAD_NUMBER)
    conclusive = reached + bad
    return {
        "reached": reached,
        "bad": bad,
        "conclusive": conclusive,
        "unknown": len(rows) - conclusive,
        "accuracy": (reached / conclusive) if conclusive else None,
        "accuracy_ci": (
            report_mod.wilson_interval(reached, conclusive) if conclusive else None
        ),
    }


def _pct(value):
    return "n/a" if value is None else f"{value * 100:.0f}%"


def build(conn, csv_path: Path) -> str:
    rows = report_mod.build_report(conn)
    total_attempts = sum(r["attempts"] for r in rows)

    if total_attempts == 0:
        raise NotEnoughData(
            "No call attempts logged, so there is nothing to write a case "
            "study about. Run the pilot first: score your scripts, make the "
            "calls, and log each outcome with `log-outcome`. This generator "
            "will not emit a document with placeholder numbers."
        )

    p2 = phase2_counts(csv_path)
    acc = number_accuracy(conn)
    scored = [r for r in rows if r["score"] is not None and r["attempts"] > 0]

    out = []
    out.append("# Agentic Priming — Decatur/30035 Local Pilot")
    out.append("")
    out.append(
        "Every figure below is computed directly from the pilot's own logs "
        "(`pilot.db` and the Phase 2 output). No number here was entered by "
        "hand."
    )
    out.append("")

    out.append("## What was run")
    out.append("")
    out.append(
        "Independent auto body, collision, and tire shops within 5 miles of "
        "30035, sourced from Google Places, cross-checked against each shop's "
        "own website and a third directory, then contacted manually."
    )
    out.append("")

    if p2:
        out.append("## Sourcing and number verification")
        out.append("")
        out.append(f"- Businesses found (post franchise-exclusion): **{p2['total']}**")
        out.append(f"- Numbers `verified` (agreed across 2+ sources): **{p2['verified']}**")
        out.append(f"- Flagged `check_manually`: **{p2['check_manually']}**")
        out.append(f"- `rejected` (probable personal mobile): **{p2['rejected']}**")
        out.append("")

    out.append("## Did the verification hold up in the field?")
    out.append("")
    if acc["conclusive"] == 0:
        out.append(
            "No conclusive evidence yet — every logged attempt was a "
            "no-answer, which says nothing about whether the number was "
            "correct. Accuracy is unmeasured, not 100%."
        )
    else:
        lo, hi = acc["accuracy_ci"]
        out.append(
            f"- Calls that reached the intended business: **{acc['reached']}**"
        )
        out.append(f"- Wrong or disconnected numbers: **{acc['bad']}**")
        out.append(
            f"- **Verified-number accuracy: {_pct(acc['accuracy'])}** "
            f"(95% CI {_pct(lo)}–{_pct(hi)}, n={acc['conclusive']} conclusive)"
        )
        if acc["unknown"]:
            out.append(
                f"- {acc['unknown']} attempt(s) were inconclusive (no answer) "
                "and are excluded from the denominator."
            )
    out.append("")

    out.append("## Score vs. field outcome")
    out.append("")
    out.append("```")
    out.append(report_mod.render(rows))
    out.append("```")
    out.append("")

    out.append("## What this does and does not show")
    out.append("")
    out.append(
        f"This pilot logged **{total_attempts}** contact attempts across "
        f"**{len(scored)}** scored script variant(s)."
    )
    out.append("")

    if total_attempts < MIN_ATTEMPTS_FOR_CLAIM or len(scored) < 2:
        out.append(
            "**It does not establish that the score predicts conversion.** At "
            "this sample size the confidence intervals on each variant's "
            "booking rate overlap heavily, so any gap between variants is "
            "within noise. What this pilot demonstrates is the *method*: "
            "scripts scored before contact, outcomes logged against the exact "
            "version used, and the comparison computed rather than asserted."
        )
        out.append("")
        out.append(
            "Treat the numbers above as a baseline to build on, not as proof "
            "to sell on. Distinguishing two variants at these booking rates "
            "needs substantially more attempts per variant."
        )
    else:
        out.append(
            "Sample size is large enough for the per-variant comparison above "
            "to be worth reading, but check the reported confidence intervals "
            "before making a causal claim about the score."
        )

    return "\n".join(out) + "\n"
