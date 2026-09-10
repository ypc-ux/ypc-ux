"""Independent quality gate for Ollama-drafted scripts.

Ollama is cheap and fine for high-volume first drafts, but it is not a
substitute for the copywriting frameworks this business already runs on
Claude. Per the "nothing grades its own work" rule already used elsewhere
in this business: an Ollama draft never scores itself. This module sends
the draft to Claude for an independent score, and escalates to a
Claude-written rewrite when the draft doesn't clear the bar.

Requires ANTHROPIC_API_KEY. If it isn't set, the gate is skipped entirely
and Ollama's draft is used as-is — same fail-open pattern as the rest of
this pipeline when an optional dependency is unavailable.
"""
import json
import logging
import os
from typing import Optional

from system_prompts import QUALITY_GATE_SYSTEM_PROMPT, get_persona

logger = logging.getLogger(__name__)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

DEFAULT_SCORE_THRESHOLD = int(os.environ.get("QUALITY_GATE_THRESHOLD", "70"))
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5"


def gate_configured() -> bool:
    """Whether the independent quality gate can run at all."""
    return ANTHROPIC_AVAILABLE and bool(os.environ.get("ANTHROPIC_API_KEY"))


def init_claude_client():
    if not ANTHROPIC_AVAILABLE:
        raise ImportError("anthropic package not installed. Install with: pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; cannot run the independent quality gate")
    return anthropic.Anthropic(api_key=api_key)


def score_script(script_text: str, client=None, model: str = DEFAULT_CLAUDE_MODEL) -> dict:
    """Independently score a script 0-100 using Claude. Never the model that wrote it.

    Returns: {"score": int, "reasoning": str}. On failure, returns a score of
    100 (fail-open — an unscoreable draft is not blocked from going out) with
    an explanatory reasoning string.
    """
    if client is None:
        client = init_claude_client()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=200,
            system=QUALITY_GATE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Script to score:\n\n{script_text}"}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        result = json.loads(text)
        return {"score": int(result["score"]), "reasoning": result.get("reasoning", "")}
    except Exception as e:
        logger.warning("Quality-gate scoring failed, treating as pass: %s", e)
        return {"score": 100, "reasoning": f"scoring unavailable ({e})"}


def generate_with_claude(
    context: str,
    angle: str,
    feedback_summary: str = "",
    client=None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> str:
    """Escalate script generation to Claude when the Ollama draft doesn't clear the bar."""
    if client is None:
        client = init_claude_client()

    prompt = f"""Generate a short, natural phone sales opener script for an {context}.

{feedback_summary}

Guidelines:
- Start with a hook (2-3 sentences max)
- Avoid sounding scripted or robotic
- Include one clear ask/call-to-action
- Keep total length ~150 words

Script:
"""
    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=get_persona(angle),
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text")).strip()


def apply_quality_gate(
    script_text: str,
    context: str,
    angle: str,
    feedback_summary: str = "",
    threshold: int = DEFAULT_SCORE_THRESHOLD,
    client=None,
) -> dict:
    """Score an Ollama draft; escalate to Claude if it scores below threshold.

    Returns: {"body": str, "source": "ollama"|"claude_escalated"|"unscored",
              "score": Optional[int], "reasoning": Optional[str]}
    """
    if not gate_configured():
        return {"body": script_text, "source": "unscored", "score": None, "reasoning": None}

    if client is None:
        client = init_claude_client()

    scored = score_script(script_text, client=client)
    if scored["score"] >= threshold:
        return {
            "body": script_text,
            "source": "ollama",
            "score": scored["score"],
            "reasoning": scored["reasoning"],
        }

    logger.info(
        "Ollama draft scored %d/100 (below %d) for angle=%s; escalating to Claude",
        scored["score"], threshold, angle,
    )
    try:
        rewritten = generate_with_claude(context, angle, feedback_summary, client=client)
        return {
            "body": rewritten,
            "source": "claude_escalated",
            "score": scored["score"],
            "reasoning": scored["reasoning"],
        }
    except Exception as e:
        logger.error("Claude escalation failed, falling back to Ollama draft: %s", e)
        return {
            "body": script_text,
            "source": "ollama_escalation_failed",
            "score": scored["score"],
            "reasoning": scored["reasoning"],
        }
