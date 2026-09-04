import json
import time
import random as _random

import google.generativeai as genai

from backend.config import GEMINI_API_KEY, USE_MOCK_LLM
from backend.data.failure_taxonomy import FAILURE_TAXONOMY, METHOD_COMPATIBLE_CODES

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

CLASSIFIABLE_CODES = [code for code in FAILURE_TAXONOMY if code != "AMBIGUOUS"]


def classify_payment(payment: dict) -> dict:
    if payment["failure_code"] != "AMBIGUOUS":
        return {
            "resolved_code": payment["failure_code"],
            "method": "RULE_BASED",
            "confidence": 1.0,
            "reasoning": "Clean failure code provided by gateway.",
        }
    return classify_with_llm(payment["raw_gateway_message"], payment["payment_method"])


def classify_with_llm(
    raw_message: str, payment_method: str, max_attempts: int = 3
) -> dict:
    if USE_MOCK_LLM:
        return mock_classify(raw_message, payment_method)

    allowed_codes = METHOD_COMPATIBLE_CODES.get(payment_method, CLASSIFIABLE_CODES)
    prompt = build_prompt(raw_message, payment_method, allowed_codes)

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

            if parsed["code"] not in allowed_codes:
                return {
                    "resolved_code": "RISK_BLOCKED",
                    "method": "LLM_FAILED_FALLBACK",
                    "confidence": 0.0,
                    "reasoning": f"LLM returned a code incompatible with payment method: {parsed['code']}",
                }

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
                time.sleep(5**attempt)
            else:
                return {
                    "resolved_code": "RISK_BLOCKED",
                    "method": "LLM_API_ERROR_FALLBACK",
                    "confidence": 0.0,
                    "reasoning": f"Gemini API call failed after {max_attempts} attempts: {str(e)[:100]}",
                }


def mock_classify(raw_message: str, payment_method: str) -> dict:
    allowed_codes = METHOD_COMPATIBLE_CODES.get(payment_method, CLASSIFIABLE_CODES)
    fake_code = _random.choice(allowed_codes)
    return {
        "resolved_code": fake_code,
        "method": "LLM_MOCK",
        "confidence": round(_random.uniform(0.7, 0.95), 2),
        "reasoning": f"[MOCK] Simulated classification based on: '{raw_message[:40]}...'",
    }


def build_prompt(raw_message: str, payment_method: str, allowed_codes: list) -> str:
    code_descriptions = "\n".join(
        f"- {code}: {FAILURE_TAXONOMY[code]['description']}" for code in allowed_codes
    )

    return f"""You are a payment failure classification system for a fintech company.

This payment was made via {payment_method}. Classify the following raw
bank/gateway failure message into exactly ONE of these categories, which
are the only categories plausible for a {payment_method} payment:

{code_descriptions}

Raw message: "{raw_message}"

Respond with ONLY a valid JSON object, no other text, in this exact format:
{{"code": "ONE_OF_THE_CODES_ABOVE", "confidence": 0.0_to_1.0, "reasoning": "one short sentence"}}"""
