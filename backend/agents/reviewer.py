import json
import time

import random as _random
import google.generativeai as genai

from backend.config import GEMINI_API_KEY, USE_MOCK_LLM

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

REVIEWABLE_ACTIONS = {
    "IMMEDIATE_RETRY",
    "DELAYED_RETRY",
    "NOTIFY_AND_RETRY",
    "SUGGEST_ALT_METHOD",
}

ACTION_DEFINITIONS = {
    "IMMEDIATE_RETRY": "Retry the payment right away, same method, no delay.",
    "DELAYED_RETRY": "Wait before retrying (hours to a full day, depending on the failure type), then retry automatically - not immediate.",
    "NOTIFY_AND_RETRY": "The customer is notified first (e.g. to re-enter an OTP), THEN a retry happens after their input - not a silent automated retry.",
    "SUGGEST_ALT_METHOD": "The customer is asked to try a different payment method - not a retry of the same method.",
}


def review_decision(payment: dict, decision: dict) -> dict:
    """
    Second agent: independently reviews the Recovery Agent's proposed
    action before it's allowed to execute. Only reviews actions that
    actually touch money/retries - already-conservative decisions
    (escalate/notify/stop) pass through unreviewed.
    """
    action = decision["action"]

    if action not in REVIEWABLE_ACTIONS:
        return {
            "approved": True,
            "final_action": action,
            "review_reasoning": "Not a reviewable action type; passed through.",
        }

    if USE_MOCK_LLM:
        return mock_review(action)

    prompt = build_review_prompt(payment, decision)

    for attempt in range(1, 4):
        try:
            model = genai.GenerativeModel("gemini-3.5-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                },
            )
            parsed = json.loads(response.text.strip())
            approved = bool(parsed["approved"])
            return {
                "approved": approved,
                "final_action": action if approved else "ESCALATE_HUMAN",
                "review_reasoning": parsed["reasoning"],
            }
        except (json.JSONDecodeError, KeyError):
            return _fallback_escalate("Reviewer returned unparseable output.")
        except Exception as e:
            if attempt < 3:
                time.sleep(3**attempt)
            else:
                return _fallback_escalate(
                    f"Reviewer API failed after 3 attempts: {str(e)[:80]}"
                )


def mock_review(action: str) -> dict:
    approved = _random.random() < 0.85  # simulate mostly-approving reviewer
    return {
        "approved": approved,
        "final_action": action if approved else "ESCALATE_HUMAN",
        "review_reasoning": "[MOCK] Simulated compliance review.",
    }


def _fallback_escalate(reason: str) -> dict:
    return {
        "approved": False,
        "final_action": "ESCALATE_HUMAN",
        "review_reasoning": f"Review unavailable, escalating for safety: {reason}",
    }


def build_review_prompt(payment: dict, decision: dict) -> str:
    action_definition = ACTION_DEFINITIONS.get(decision["action"], "")
    return f"""You are a compliance reviewer for an automated payment recovery
system. Another AI agent has proposed a recovery action. Your default is to
APPROVE - only override to escalation if you identify a SPECIFIC, concrete
concern, not general caution.

Payment details:
- Amount: {payment['currency']} {payment['amount']}
- Payment method: {payment['payment_method']}
- Diagnosed failure: {payment['resolved_failure_code']}
- Diagnosis confidence: {payment['classification_confidence']}
- Prior retry attempts: {payment['retry_count']}

Proposed action: {decision['action']}
What this action actually does: {action_definition}
Proposed reasoning: {decision['reasoning']}

Evaluate the action AS DEFINED ABOVE, not based on what the name might
suggest. Only set approved to false for a clear, specific factor (e.g.
unusually high amount for this failure type, low confidence combined with
high retry count, or a genuine mismatch between the action and the failure
type - like suggesting an alt method when the failure wasn't method-related).

Respond with ONLY a valid JSON object, no other text:
{{"approved": true_or_false, "reasoning": "one short sentence naming the specific concern, or why it's fine"}}"""
