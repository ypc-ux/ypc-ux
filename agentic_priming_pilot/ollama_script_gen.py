"""Ollama-based script generation and feedback analysis for Phase 3.

Generates phone/in-person sales opener scripts using local Ollama LLM.
Supports adaptive regeneration based on booking performance feedback.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from system_prompts import get_persona, ANALYSIS_SYSTEM_PROMPT, REGENERATION_SYSTEM_PROMPT
from quality_gate import apply_quality_gate, gate_configured


def init_ollama_client(base_url: str = "http://localhost:11434"):
    """Create and test Ollama client connection.

    Args:
        base_url: Ollama API endpoint (default localhost with standard port)

    Returns:
        ollama.Client instance

    Raises:
        ConnectionError: If Ollama server is unreachable
        ImportError: If ollama package not installed
    """
    if not OLLAMA_AVAILABLE:
        raise ImportError(
            "ollama package not installed. Install with: pip install ollama"
        )

    client = ollama.Client(host=base_url)
    try:
        client.list()
        logger.info(f"Connected to Ollama at {base_url}")
        return client
    except Exception as e:
        raise ConnectionError(
            f"Cannot reach Ollama at {base_url}. "
            "Is the daemon running? (ollama serve)"
        ) from e


def generate_scripts(
    context: str,
    num_variants: int = 2,
    feedback: Optional[list] = None,
    model: str = "mistral",
    temperature: float = 0.7,
    client = None,
) -> list:
    """Generate N script variants with optional feedback context.

    Args:
        context: Description of the target (e.g., "auto body shop owner in Atlanta")
        num_variants: Number of distinct script versions to generate
        feedback: Optional list of dicts with booking feedback:
                  [{"outcome": "booked", "note": "quick decision maker"},
                   {"outcome": "declined", "objection": "don't need work"}]
        model: Ollama model to use (default: mistral)
        temperature: LLM temperature (0.0-1.0, higher = more creative)
        client: Ollama client (initialized if None)

    Returns:
        List of dicts with keys: id, variant_num, body, prompt_seed, model, temperature
    """
    if client is None:
        client = init_ollama_client()

    feedback_summary = ""
    if feedback:
        booked = [f["note"] for f in feedback if f.get("outcome") == "booked"]
        declined = [f["objection"] for f in feedback if f.get("outcome") == "declined"]
        feedback_summary = "Previous feedback:\n"
        if booked:
            feedback_summary += f"  ✓ Booked: {', '.join(booked[:2])}\n"
        if declined:
            feedback_summary += f"  ✗ Declined because: {', '.join(declined[:2])}\n"

    variants = []
    for i in range(num_variants):
        angle = _pick_angle(i, booked_count=len([f for f in (feedback or []) if f.get("outcome") == "booked"]))

        prompt = f"""Generate a short, natural phone sales opener script for an {context}.

{feedback_summary}

This is variant {i + 1}.

Guidelines:
- Start with a hook (2-3 sentences max)
- Avoid sounding scripted or robotic
- Include one clear ask/call-to-action
- Keep total length ~150 words

Script:
"""

        try:
            response = client.generate(
                model=model,
                prompt=prompt,
                system=get_persona(angle),
                stream=False,
                options={"temperature": temperature, "num_predict": 500},
            )
            body = response.get("response", "").strip()

            if not body or len(body) < 20:
                logger.warning(f"Ollama generated empty/short script for variant {i+1}")
                body = _fallback_script(context, angle)

            gated = _run_quality_gate(body, context, angle, feedback_summary)

            variants.append({
                "id": i + 1,
                "variant_num": i + 1,
                "body": gated["body"],
                "prompt_seed": angle,
                "model": model,
                "temperature": temperature,
                "source": gated["source"],
                "quality_score": gated["score"],
            })
            logger.info(
                f"Generated script variant {i+1} ({angle}), source={gated['source']}"
                + (f", score={gated['score']}" if gated["score"] is not None else "")
            )
        except Exception as e:
            logger.error(f"Error generating variant {i+1}: {e}")
            variants.append({
                "id": i + 1,
                "variant_num": i + 1,
                "body": _fallback_script(context, angle),
                "prompt_seed": angle,
                "model": model,
                "temperature": temperature,
                "source": "fallback_template",
                "quality_score": None,
            })

    return variants


def analyze_booking_feedback(attempts: list, client=None) -> dict:
    """Analyze booking attempt records to extract patterns.

    Args:
        attempts: List of dicts from phase3.store.attempts table with keys:
                  business_name, outcome, notes, contacted_at
        client: Ollama client (initialized if None)

    Returns:
        Dict with keys: booked_count, declined_count, common_objections,
                        best_opener_angle, suggested_angle, low_quality_reasons
    """
    if client is None:
        try:
            client = init_ollama_client()
        except Exception:
            logger.warning("Ollama unavailable; using heuristic analysis")
            client = None

    if not attempts:
        return {
            "booked_count": 0,
            "declined_count": 0,
            "common_objections": [],
            "best_opener_angle": "value_prop",
            "suggested_angle": "value_prop",
            "low_quality_reasons": []
        }

    booked = [a for a in attempts if a.get("outcome") == "booked"]
    declined = [a for a in attempts if a.get("outcome") == "declined"]

    feedback_text = "\n".join([
        f"Booked: {b.get('notes', '')}" for b in booked[:3]
    ] + [
        f"Declined: {d.get('notes', '')}" for d in declined[:3]
    ])

    if client:
        prompt = f"""Analyze these call attempt notes and suggest script improvements.

Attempts:
{feedback_text}

Provide a JSON response with:
- common_objections: list of top 2-3 objections mentioned
- best_approach: one word or phrase that worked (e.g., "quick_decision", "urgency")
- next_angle: what to emphasize next (e.g., "ROI", "speed", "social_proof")

Response must be valid JSON only, no other text."""

        try:
            response = client.generate(
                model="mistral",
                prompt=prompt,
                system=ANALYSIS_SYSTEM_PROMPT,
                stream=False,
                options={"temperature": 0.3},
            )
            try:
                result = json.loads(response.get("response", "{}"))
            except json.JSONDecodeError:
                result = _extract_json(response.get("response", ""))
        except Exception as e:
            logger.error(f"Ollama analysis failed: {e}")
            result = {}
    else:
        result = {}

    return {
        "booked_count": len(booked),
        "declined_count": len(declined),
        "common_objections": result.get("common_objections", []),
        "best_opener_angle": result.get("best_approach", "value_prop"),
        "suggested_angle": result.get("next_angle", "urgency"),
        "low_quality_reasons": result.get("issues", []),
    }


def regenerate_based_on_feedback(
    old_script: str,
    feedback: dict,
    context: str = "auto body shop owner",
    script_context: str = "phone",
    model: str = "mistral",
    client=None,
) -> str:
    """Refine a script based on booking feedback patterns.

    Args:
        old_script: Previous script body
        feedback: Dict from analyze_booking_feedback()
        context: Target customer description
        script_context: "phone" or "in_person"
        model: Ollama model to use
        client: Ollama client (initialized if None)

    Returns:
        Improved script body
    """
    if client is None:
        try:
            client = init_ollama_client()
        except Exception:
            logger.warning("Ollama unavailable; returning original script")
            return old_script

    angle = feedback.get("suggested_angle", "urgency")
    objections = ", ".join(feedback.get("common_objections", [])[:2])

    prompt = f"""You are improving a sales phone opener script.

Original script:
{old_script}

Feedback from real calls:
- Common objections: {objections or "none recorded yet"}
- What worked: {feedback.get('best_opener_angle', 'initial contact')}
- Next focus: {angle}
- Booked: {feedback['booked_count']}, Declined: {feedback['declined_count']}

Rewrite the script to:
1. Address the top objection early
2. Emphasize {angle}
3. Keep same tone and length
4. Stay appropriate for {script_context}

Improved script:
"""

    try:
        response = client.generate(
            model=model,
            prompt=prompt,
            system=REGENERATION_SYSTEM_PROMPT,
            stream=False,
            options={"temperature": 0.5, "num_predict": 500},
        )
        improved = response.get("response", "").strip()

        if len(improved) < 20:
            logger.warning("Generated script too short; returning original")
            return old_script

        logger.info(f"Regenerated script with angle={angle}")
        return improved
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        return old_script


def _run_quality_gate(body: str, context: str, angle: str, feedback_summary: str) -> dict:
    """Run the independent Claude quality gate on an Ollama draft, if configured.

    Returns {"body", "source", "score"}. If the gate isn't configured
    (no ANTHROPIC_API_KEY), the draft passes through unscored.
    """
    if not gate_configured():
        return {"body": body, "source": "ollama_unscored", "score": None}

    try:
        gated = apply_quality_gate(body, context, angle, feedback_summary)
        return {"body": gated["body"], "source": gated["source"], "score": gated["score"]}
    except Exception as e:
        logger.warning(f"Quality gate errored, using Ollama draft as-is: {e}")
        return {"body": body, "source": "ollama_gate_error", "score": None}


def _pick_angle(variant_num: int, booked_count: int = 0) -> str:
    """Heuristically pick an angle for this variant based on iteration."""
    angles = [
        "value_prop",      # Lead with ROI/time savings
        "urgency",         # Emphasize time-sensitive opportunity
        "social_proof",    # Reference similar shops you've helped
        "ease",            # Easy decision, low risk
        "personalized",    # Mention their specific situation
    ]
    return angles[variant_num % len(angles)]


def _fallback_script(context: str, angle: str) -> str:
    """Fallback script when Ollama unavailable."""
    scripts = {
        "value_prop": f"""Hi, this is [Your Name] with [Company].
I help {context}s reduce downtime and increase customer satisfaction through [solution].
Do you have 30 seconds to hear how we've helped shops like yours save time and money?""",
        "urgency": f"""Hi, quick question — is this an okay time?
I'm reaching out because we have limited availability this month for {context}s in your area.
We help shops like yours [quick benefit]. Worth a quick conversation?""",
        "social_proof": f"""Hi, [Name], I'm reaching out because several {context}s near you have recently [achieved outcome].
We help shops like yours [key benefit].
Would a 15-minute chat make sense?""",
        "ease": f"""Hi, this is [Your Name] from [Company].
One quick question: are you open to exploring ways to improve [pain point]?
No commitment needed — just a 10-minute chat.""",
        "personalized": f"""Hi, I noticed your shop [observed detail about their business].
That's exactly what we help {context}s with.
Quick question — is this a good time for a brief call?""",
    }
    return scripts.get(angle, scripts["value_prop"])


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction from text."""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {}
