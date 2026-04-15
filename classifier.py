"""AI hazard classifier using Groq API with keyword fallback."""

import json
import logging
import os
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
CONFIDENCE_THRESHOLD = 0.6

CLASSIFICATION_PROMPT = """You are a traffic hazard classifier for urban commuters.
Analyze the following social media post and respond ONLY with a JSON object.
Do NOT include any explanation, markdown, or extra text — just the raw JSON.

Required JSON format:
{{"is_hazard": true/false, "category": "Flood|Accident|Obstruction|Protest|HazMat|Traffic|None", "severity": "LOW|MEDIUM|HIGH", "confidence": 0.0-1.0}}

Rules:
- "is_hazard" is true only if the post describes an active danger or major disruption.
- "category" must be one of the listed values. Use "None" for non-hazards.
- "severity": HIGH = life-threatening or full road closure; MEDIUM = significant delay; LOW = minor issue.
- "confidence" is your certainty from 0.0 to 1.0.

Post to classify:
"{text}"
"""

KEYWORD_RULES: list[tuple[list[str], str, str, float]] = [
    (["flood", "water", "submerge", "waterlog"], "Flood", "HIGH", 0.85),
    (["accident", "crash", "collide", "collision", "overturn"], "Accident", "HIGH", 0.82),
    (["tree", "block", "obstruct", "fell", "fallen"], "Obstruction", "MEDIUM", 0.78),
    (["protest", "rally", "march", "demonstrat", "gather"], "Protest", "MEDIUM", 0.75),
    (["gas", "leak", "hazmat", "chemical", "fire", "smoke"], "HazMat", "HIGH", 0.88),
    (["slow", "delay", "congesti", "jam", "traffic"], "Traffic", "LOW", 0.65),
]


def _keyword_fallback(text: str) -> dict[str, Any]:
    """Classify a post using keyword matching when Groq is unavailable."""
    text_lower = text.lower()
    for keywords, category, severity, confidence in KEYWORD_RULES:
        if any(kw in text_lower for kw in keywords):
            return {
                "is_hazard": category != "Traffic" or "jam" in text_lower,
                "category": category,
                "severity": severity,
                "confidence": confidence,
            }
    return {
        "is_hazard": False,
        "category": "None",
        "severity": "LOW",
        "confidence": 0.95,
    }


def _strip_markdown_fences(raw: str) -> str:
    """Remove markdown code fences from an LLM response."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"```", "", cleaned)
    return cleaned.strip()


def _parse_llm_response(raw: str) -> Optional[dict[str, Any]]:
    """Safely parse the LLM JSON response."""
    try:
        cleaned = _strip_markdown_fences(raw)
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Failed to parse LLM response: %s — %s", exc, raw[:200])
        return None


async def classify_post(text: str) -> Optional[dict[str, Any]]:
    """Classify a social media post as a traffic hazard or not.

    Returns the classification dict or None if confidence is below threshold.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    result = await _classify_via_groq(text, api_key) if api_key else None

    if result is None:
        logger.info("Using keyword fallback for classification")
        result = _keyword_fallback(text)

    if result.get("confidence", 0) < CONFIDENCE_THRESHOLD:
        logger.info("Classification rejected — confidence %.2f below threshold", result["confidence"])
        return None

    return result


async def _classify_via_groq(text: str, api_key: str) -> Optional[dict[str, Any]]:
    """Call the Groq API to classify a post."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": CLASSIFICATION_PROMPT.format(text=text)},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(GROQ_API_URL, json=payload, headers=headers)
            response.raise_for_status()
        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        return _parse_llm_response(raw_content)
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.error("Groq API call failed: %s", exc)
        return None
