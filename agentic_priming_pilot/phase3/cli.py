"""Phase 3 CLI: register script variants, capture pre-call baseline scores,
log real call outcomes, and report score against conversion.

    python -m phase3.cli add-script --name opener-a --context phone --file opener.txt
    python -m phase3.cli score 1 --backend manual --total 72 --humanity pass
    python -m phase3.cli log-outcome 1 --business "Ray's Body Shop" --outcome booked
    python -m phase3.cli report
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from . import call_executor
from . import case_study
from . import ollama_integration
from . import report as report_mod
from . import scorer, store


def _load_verified_phones(csv_path: Path) -> dict:
    """Map E.164 phone -> business name for rows Phase 2 marked verified."""
    if not csv_path.exists():
        return {}
    verified = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("confidence") != "verified":
                continue
            for key in ("phone_gbp", "phone_website", "phone_third_source"):
                if row.get(key):
                    verified[row[key]] = row.get("business_name", "")
    return verified


def cmd_add_script(conn, args):
    body = (
        Path(args.file).read_text()
        if args.file
        else sys.stdin.read()
    ).strip()
    if not body:
        sys.exit("Script body is empty.")
    script_id = store.add_script(conn, args.name, args.context, body)
    print(f"Added script version {script_id}: {args.name} ({args.context})")
    print("Score it before making any calls:")
    print(f"  python -m phase3.cli score {script_id} --backend manual ...")


def cmd_list(conn, args):
    for row in store.list_scripts(conn):
        baseline = store.latest_baseline(conn, row["id"])
        score = f"{baseline['total_score']:.1f}" if baseline else "unscored"
        print(f"{row['id']:>3}  {row['name']:<24} {row['context']:<10} {score}")


def cmd_score(conn, args):
    script = store.get_script(conn, args.script_id)

    if args.backend == "http":
        result = scorer.score_http(script["body"], script["context"])
    else:
        if args.total is None or args.humanity is None:
            sys.exit(
                "Manual backend requires --total and --humanity (pass|fail), "
                "taken from a real run of the Agentic Priming scorer."
            )
        gate_flags = json.loads(args.gate_flags) if args.gate_flags else {}
        result = scorer.score_manual(
            total_score=args.total,
            humanity_check=(args.humanity == "pass"),
            gate_flags=gate_flags,
            scorer_version=args.scorer_version,
        )

    baseline_id = store.record_baseline(conn, script["id"], result)
    print(
        f"Baseline {baseline_id} recorded for script {script['id']} "
        f"({script['name']}, {script['context']}):"
    )
    print(f"  total_score    {result.total_score}")
    print(f"  humanity_check {'pass' if result.humanity_check else 'FAIL'}")
    print(f"  gate_flags     {result.gate_flags or '{}'}")
    print(f"  backend        {result.backend}")
    if not result.humanity_check:
        print(
            "\nHumanity check FAILED — fix the script before using it, "
            "rather than logging outcomes against it."
        )


def cmd_log_outcome(conn, args):
    script = store.get_script(conn, args.script_id)

    if args.phone and args.targets:
        verified = _load_verified_phones(Path(args.targets))
        if verified and args.phone not in verified:
            print(
                f"WARNING: {args.phone} is not a 'verified' row in "
                f"{args.targets}. Phase 2 only clears verified numbers for "
                "calling — double-check before logging this.",
                file=sys.stderr,
            )

    attempt_id = store.record_attempt(
        conn,
        script_version_id=script["id"],
        business_name=args.business,
        phone=args.phone or "",
        channel=args.channel,
        outcome=args.outcome,
        notes=args.notes or "",
    )
    print(
        f"Logged attempt {attempt_id}: {args.business} -> {args.outcome} "
        f"(script {script['id']}, {script['name']})"
    )


def cmd_report(conn, args):
    rows = report_mod.build_report(conn)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(report_mod.render(rows))


def cmd_case_study(conn, args):
    doc = case_study.build(conn, Path(args.targets))
    if args.out:
        Path(args.out).write_text(doc)
        print(f"Wrote case study to {args.out}")
    else:
        print(doc)


def cmd_batch_call(conn, args):
    """Load shops from CSV, run batch calls via call_executor, log outcomes."""
    shops = ollama_integration.load_shops_csv(args.csv)
    if not shops:
        sys.exit(f"No verified shops found in {args.csv}")

    script = store.get_script(conn, args.script_id)
    limit = args.limit or len(shops)

    print(f"Calling {min(limit, len(shops))} shops with script {script['id']} ({script['name']})...")

    outcomes = call_executor.batch_call_shops(
        shops=shops,
        script_id=script["id"],
        script_body=script["body"],
        batch_size=limit,
        channel=args.channel,
    )

    result = ollama_integration.log_outcomes_bulk(conn, outcomes)
    print(f"Done: {result['recorded_count']} recorded, {result['failed_count']} failed")

    for o in outcomes:
        status = "✓" if o["outcome"] == "booked" else "✗"
        print(f"  {status} {o['business_name']}: {o['outcome']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(store.DEFAULT_DB))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-script", help="Register a script variant.")
    p.add_argument("--name", required=True)
    p.add_argument("--context", required=True, choices=store.CONTEXTS)
    p.add_argument("--file", help="Read script body from file (else stdin).")
    p.set_defaults(func=cmd_add_script)

    p = sub.add_parser("list", help="List script variants and their scores.")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("score", help="Record a pre-call baseline score.")
    p.add_argument("script_id", type=int)
    p.add_argument("--backend", choices=("manual", "http"), default="manual")
    p.add_argument("--total", type=float, help="Total score (manual backend).")
    p.add_argument("--humanity", choices=("pass", "fail"))
    p.add_argument("--gate-flags", dest="gate_flags", help='JSON object.')
    p.add_argument("--scorer-version", dest="scorer_version")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("log-outcome", help="Log a real call/walk-up outcome.")
    p.add_argument("script_id", type=int)
    p.add_argument("--business", required=True)
    p.add_argument("--phone")
    p.add_argument("--channel", choices=("phone", "walk_in"), default="phone")
    p.add_argument("--outcome", required=True, choices=store.OUTCOMES)
    p.add_argument("--notes")
    p.add_argument(
        "--targets",
        default="shops.csv",
        help="Phase 2 CSV, used to warn if the number wasn't verified.",
    )
    p.set_defaults(func=cmd_log_outcome)

    p = sub.add_parser("report", help="Score vs conversion comparison.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser(
        "case-study", help="Generate the case study from logged data."
    )
    p.add_argument("--targets", default="shops.csv")
    p.add_argument("--out", help="Write to file (default: stdout).")
    p.set_defaults(func=cmd_case_study)

    p = sub.add_parser("batch-call", help="Run batch calls and log outcomes.")
    p.add_argument("script_id", type=int)
    p.add_argument("--csv", default="shops.csv", help="Shops CSV (Phase 2 output).")
    p.add_argument("--limit", type=int, help="Max shops to call (default: all).")
    p.add_argument("--channel", choices=("phone", "walk_in"), default="phone")
    p.set_defaults(func=cmd_batch_call)

    args = parser.parse_args(argv)
    conn = store.connect(Path(args.db))
    try:
        args.func(conn, args)
    except (
        scorer.ScorerUnavailable,
        case_study.NotEnoughData,
        LookupError,
        ValueError,
    ) as exc:
        sys.exit(f"error: {exc}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
