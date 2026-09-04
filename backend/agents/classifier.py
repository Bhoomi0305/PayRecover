import json
import time
import random as _random  # aliased to avoid clashing with any other 'random' usage later
import google.generativeai as genai

from backend.config import GEMINI_API_KEY, USE_MOCK_LLM
from backend.data.failure_taxonomy import FAILURE_TAXONOMY

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


CLASSIFIABLE_CODES = [code for code in FAILURE_TAXONOMY if code != "AMBIGUOUS"]


def classify_payment(payment: dict) -> dict:
    """
    Resolve a payment's true failure_code.
    If it's already a clean code, use fast rule-based lookup (no API cost).
    If it's AMBIGUOUS, call the LLM to interpret the raw message.
    """
    if payment["failure_code"] != "AMBIGUOUS":
        return {
            "resolved_code": payment["failure_code"],
            "method": "RULE_BASED",
            "confidence": 1.0,
            "reasoning": "Clean failure code provided by gateway.",
        }

    return classify_with_llm(payment["raw_gateway_message"])


def classify_with_llm(raw_message: str, max_attempts: int = 3) -> dict:
    if USE_MOCK_LLM:
        return mock_classify(raw_message)

    prompt = build_prompt(raw_message)

    for attempt in range(1, max_attempts + 1):
        try:
            model = genai.GenerativeModel("gemini-3.5-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                },
            )
            raw_output = response.text.strip()
            parsed = json.loads(raw_output)
            return {
                "resolved_code": parsed["code"],
                "method": "LLM",
                "confidence": parsed["confidence"],
                "reasoning": parsed["reasoning"],
            }
        except (json.JSONDecodeError, KeyError):
            return {
                "resolved_code": "RISK_BLOCKED",
                "method": "LLM_FAILED_FALLBACK",
                "confidence": 0.0,
                "reasoning": "Could not parse LLM output.",
            }
        except Exception as e:
            if attempt < max_attempts:
                wait = 5**attempt
                print(
                    f"  Attempt {attempt} failed ({str(e)[:60]}), retrying in {wait}s..."
                )
                time.sleep(wait)
            else:
                return {
                    "resolved_code": "RISK_BLOCKED",
                    "method": "LLM_API_ERROR_FALLBACK",
                    "confidence": 0.0,
                    "reasoning": f"Gemini API call failed after {max_attempts} attempts: {str(e)[:100]}",
                }


def mock_classify(raw_message: str) -> dict:
    """Fake LLM response for testing the pipeline without real API calls/costs."""
    fake_code = _random.choice(CLASSIFIABLE_CODES)
    return {
        "resolved_code": fake_code,
        "method": "LLM_MOCK",
        "confidence": round(_random.uniform(0.7, 0.95), 2),
        "reasoning": f"[MOCK] Simulated classification based on: '{raw_message[:40]}...'",
    }


def build_prompt(raw_message: str) -> str:
    code_descriptions = "\n".join(
        f"- {code}: {FAILURE_TAXONOMY[code]['description']}"
        for code in CLASSIFIABLE_CODES
    )

    return f"""You are a payment failure classification system for a fintech company.

Classify the following raw bank/gateway failure message into exactly ONE of these categories:

{code_descriptions}

Raw message: "{raw_message}"

Respond with ONLY a valid JSON object, no other text, in this exact format:
{{"code": "ONE_OF_THE_CODES_ABOVE", "confidence": 0.0_to_1.0, "reasoning": "one short sentence"}}"""
