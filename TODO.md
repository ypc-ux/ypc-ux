# Open items — handoff from Claude session

Picking work back up in VS Code. State of things as of this handoff:

## 1. Wire `call_executor.py` into the CLI

`agentic_priming_pilot/phase3/call_executor.py` is fully built (outcome
simulation, batch dialing, quality heuristics) but not imported anywhere in
the repo. Its `batch_call_shops()` return shape already matches what
`ollama_integration.log_outcomes_bulk(conn, outcomes)` expects field-for-field.

Fix: add a `cmd_batch_call` command to `phase3/cli.py` that loads shops from
a CSV, calls `call_executor.batch_call_shops(...)`, and pipes the result into
`ollama_integration.log_outcomes_bulk(conn, outcomes)`. Double-check
`store.OUTCOMES` actually includes `booked`/`declined`/`no_answer`/`hung_up`
before wiring it up — `record_attempt` raises `ValueError` otherwise.

## 2. Act on the `jbuilds` hosting audit

`jbuilds/docs/HOSTING_PLATFORM_AUDIT.md` has recommendations for all 16
repos (6 → Vercel, 3 → Supabase/Vercel Postgres, 5 → GitHub Pages, 2 →
specialized). Nothing has actually been migrated yet — it's still just the
audit doc.

## 3. Verify the `ops` digest repo in production

`ops` (zero-secret GitHub Issues delivery, see its `digest/github_notify.py`)
was built and verified once with a live test (two issues created, then
closed as verification artifacts). Hasn't been watched running for real on
its actual schedule yet.

## 4. Attach `humanizer-influence` if you want its real voice logic

It's private and was never attached to any Claude session, so all tweet/email
copy so far is an approximation of your voice, not driven by that tool's
actual logic. Attach it if you want that swapped in for real.

---

## Also still open (not code — needs manual follow-through, not a code fix)

- **Tweet Queue** (Notion): https://app.notion.com/p/85e328f2738a418aa90bf1713c044737
  — several drafts sitting in `Draft` status, need review/approval, and there's
  no X/Twitter connector anywhere, so posting is manual either way.
- **Kallaway → Twitter Playbook** (Notion): https://app.notion.com/p/3d70f24cbc0581a4974fc481d99e7d60
  — grows every time a new Kallaway video transcript gets pasted in.
- **Fleet Dashboard** (Artifact): https://claude.ai/code/artifact/509fb23f-7eea-4d48-98a6-ceb2c28d6df2
  — live status board for all repos; statuses are manually seeded, not
  auto-synced to real GitHub activity.
- **Hourly tweet-draft routine** — was running bound to a specific Claude
  session, checking for new pushes and drafting tweets + emailing
  1juliusyoung@gmail.com. Session-bound routines don't carry over to a new
  environment (like VS Code) — if this cadence still matters, it needs to be
  rebuilt either as a scheduled routine from wherever you're working next, or
  as a GitHub Action / cron job that lives in a repo instead.
