"""
Optional plain-language explanation of a risk score, written by an LLM.

The score and the risk band are computed by model.py and are never changed
here. The LLM only receives the numbers behind the score (no names, IDs or
other personal details) and writes a short explanation for the loan officer.

If anything goes wrong (no key, timeout, error, empty answer),
generate_explanation returns None and the app shows its built-in explanation
instead, so the AI can never break an assessment.

Settings (environment variables):
  GEMINI_API_KEY   key from Google AI Studio. Without it the feature is off.
  GEMINI_MODEL     optional, defaults to gemini-3.5-flash-lite
"""

import logging
import os

import requests

from model import WEIGHTS

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
TIMEOUT_SECONDS = 8
MAX_CHARS = 700

LABELS = {
    "txn_regularity": "Transaction regularity",
    "utility_payment_score": "Utility bill payments",
    "income_score": "Monthly income",
    "mobile_usage_stability": "Mobile usage stability",
    "social_signal_score": "Social signal",
}


def next_band(score: float):
    """Returns (points needed, name of the next band), or None in the top band."""
    if score < 40:
        return round(40 - score, 2), "Medium Risk"
    if score < 70:
        return round(70 - score, 2), "Low Risk"
    return None


def build_prompt(inputs: dict, result: dict) -> str:
    """Builds the request text. It contains numbers only."""
    points = "\n".join(
        f"- {LABELS[key]}: {round(earned, 2):g} of {round(WEIGHTS[key] * 100, 2):g} points"
        for key, earned in result["breakdown"].items()
    )

    values = (
        f"- Transaction regularity: {inputs['txn_regularity']:g} out of 100\n"
        f"- Utility bill payments: {inputs['utility_payment_score']:g} out of 100\n"
        f"- Average monthly income: Rs {inputs['avg_monthly_inflow']:,.0f}\n"
        f"- Mobile usage stability: {inputs['mobile_usage_stability']:g} out of 100\n"
        f"- Social signal: {inputs['social_signal_score']:g} out of 100"
    )

    gap = next_band(result["final_score"])
    if gap:
        gap_line = f"Points needed to reach {gap[1]}: {gap[0]:g}"
    else:
        gap_line = "The borrower is already in the best band (Low Risk)."

    return (
        "You are helping a loan officer understand a credit risk score for a "
        "borrower who has no credit file.\n"
        "The score was computed by a fixed scorecard. Do not change, question "
        "or recompute it.\n\n"
        f"Score: {result['final_score']:g} out of 100 ({result['risk_band']}).\n"
        "Bands: 70 or more is Low Risk, 40 up to 70 is Medium Risk, below 40 "
        "is High Risk.\n"
        f"{gap_line}\n\n"
        f"Points each signal contributed:\n{points}\n\n"
        f"Values entered for the borrower:\n{values}\n\n"
        "Write a plain-English explanation of 2 to 3 sentences for the loan "
        "officer:\n"
        "- say which signals helped the most and which held the score back\n"
        "- say what would move the borrower to the next band, if there is one\n"
        "- use only the numbers above and do not invent facts about the borrower\n"
        "- do not recommend approving or rejecting a loan\n"
        "- no headings, no bullet points, no markdown"
    )


def generate_explanation(inputs: dict, result: dict):
    """Returns a short explanation, or None if the AI is unavailable."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    body = {
        "contents": [{"parts": [{"text": build_prompt(inputs, result)}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }

    try:
        response = requests.post(
            f"{API_BASE}/{model}:generateContent",
            # The key travels in a header, so it never appears in a URL or a log.
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        logger.warning("AI explanation unavailable: %s", type(error).__name__)
        return None

    text = " ".join(str(text).split())
    if not text:
        return None

    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        last_stop = cut.rfind(". ")
        text = cut[: last_stop + 1] if last_stop > 0 else cut

    return text
