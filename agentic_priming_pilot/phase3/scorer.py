"""Adapter layer between the pilot and the Agentic Priming 87-heuristic scorer.

The scorer itself is NOT implemented here and must not be. Its heuristics,
gate families, and humanity check are the actual product; a local
reimplementation would produce authoritative-looking numbers that are in fact
invented, which would silently invalidate the whole point of the pilot
(proving the score predicts real-world conversion).

Two honest backends are provided:

  http    Calls a real Agentic Priming scoring endpoint. Configure with
          AGENTIC_PRIMING_API_URL (and optionally AGENTIC_PRIMING_API_KEY).
          The response mapping below is a best guess at the payload shape —
          adjust `_from_http_payload` once the real contract is known.

  manual  You run the script through the real scorer yourself (UI, notebook,
          whatever you have) and type the numbers in. Slower, but the values
          are real, which is the only thing that matters for the case study.

There is intentionally no "estimate" or "simulate" backend.
"""
import os
from dataclasses import dataclass, field
from typing import Optional

import requests

DEFAULT_TIMEOUT = 30


class ScorerUnavailable(RuntimeError):
    """Raised when no real scorer is reachable. Never fall back to a guess."""


@dataclass
class ScoreResult:
    total_score: float
    gate_flags: dict
    humanity_check: bool
    backend: str
    scorer_version: Optional[str] = None
    raw: dict = field(default_factory=dict)


def _from_http_payload(payload: dict, backend: str) -> ScoreResult:
    """Map an API response onto ScoreResult.

    Tolerant about key naming because the exact contract isn't pinned down
    yet; raises rather than defaulting when a required field is missing, so a
    contract mismatch surfaces loudly instead of silently scoring 0.
    """
    score = payload.get("total_score", payload.get("score"))
    if score is None:
        raise ScorerUnavailable(
            "Scorer response had no 'total_score'/'score' field. "
            f"Got keys: {sorted(payload)}. Update _from_http_payload() to "
            "match the real API contract."
        )

    humanity = payload.get("humanity_check", payload.get("humanity"))
    if isinstance(humanity, dict):
        humanity = humanity.get("pass", humanity.get("passed"))
    if humanity is None:
        raise ScorerUnavailable(
            "Scorer response had no humanity check result. "
            f"Got keys: {sorted(payload)}."
        )
    if isinstance(humanity, str):
        humanity = humanity.strip().lower() in ("pass", "passed", "true", "yes")

    gate_flags = payload.get("gate_flags", payload.get("gates", {}))
    if isinstance(gate_flags, list):
        gate_flags = {str(flag): True for flag in gate_flags}

    return ScoreResult(
        total_score=float(score),
        gate_flags=dict(gate_flags),
        humanity_check=bool(humanity),
        backend=backend,
        scorer_version=payload.get("version", payload.get("scorer_version")),
        raw=payload,
    )


def score_http(script_body: str, context: str) -> ScoreResult:
    base_url = os.environ.get("AGENTIC_PRIMING_API_URL", "").rstrip("/")
    if not base_url:
        raise ScorerUnavailable(
            "AGENTIC_PRIMING_API_URL is not set. Either point it at the real "
            "scoring endpoint or use the 'manual' backend and enter real "
            "scores by hand. Do not substitute an estimate."
        )
    headers = {}
    api_key = os.environ.get("AGENTIC_PRIMING_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.post(
            f"{base_url}/score",
            json={"script": script_body, "context": context},
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ScorerUnavailable(f"Scoring request failed: {exc}") from exc

    return _from_http_payload(resp.json(), backend="http")


def score_manual(
    total_score: float,
    humanity_check: bool,
    gate_flags: dict,
    scorer_version: Optional[str] = None,
) -> ScoreResult:
    """Record a score you obtained from the real scorer yourself."""
    return ScoreResult(
        total_score=float(total_score),
        gate_flags=dict(gate_flags),
        humanity_check=bool(humanity_check),
        backend="manual",
        scorer_version=scorer_version,
    )
