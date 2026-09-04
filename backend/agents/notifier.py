import json
import time

import google.generativeai as genai

from backend.config import GEMINI_API_KEY, USE_MOCK_LLM
import random as _random

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

NOTIFIABLE_STATUSES = {"PENDING_CUSTOMER_ACTION"}
NOTIFIABLE_ACTIONS = {"NOTIFY_CUSTOMER_ONLY", "NOTIFY_AND_RETRY"}


def needs_notification(payment: dict) -> bool:
    return (
        payment.get("status") in NOTIFIABLE_STATUSES
        or payment.get("recovery_action") in NOTIFIABLE_ACTIONS
    )


def generate_notification(payment: dict) -> dict:
    """
    Draft a short customer-facing message explaining the payment failure
    and next step. Falls back to a plain template if the LLM is
    unavailable - this is content generation, not a decision, so a
    template fallback is appropriate (no need to escalate to a human).
    """
    if USE_MOCK_LLM:
        return mock_notification(payment)

    prompt = build_notification_prompt(payment)

    for attempt in range(1, 3):
        try:
            model = genai.GenerativeModel("gemini-3.5-flash-lite")
            response = model.generate_content(
                prompt, generation_config={"temperature": 0.4}
            )
            return {
                "message": response.text.strip(),
                "method": "LLM",
            }
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                return template_notification(payment)


def template_notification(payment: dict) -> dict:
    reason_text = payment["resolved_failure_code"].replace("_", " ").lower()
    return {
        "message": (
            f"Hi {payment['customer_name']}, your payment of "
            f"{payment['currency']} {payment['amount']} could not be completed "
            f"due to {reason_text}. Please try again or use an alternate "
            f"payment method."
        ),
        "method": "TEMPLATE_FALLBACK",
    }


def mock_notification(payment: dict) -> dict:
    return {
        "message": f"[MOCK] Notification for {payment['payment_id']}: please retry your payment.",
        "method": "MOCK",
    }


def build_notification_prompt(payment: dict) -> str:
    return f"""Write a short, polite SMS-length message (under 200 characters) to a
customer whose payment failed. Be clear about what happened and what they
should do next. Do not use placeholders like [Name] - use the actual details
given.

Customer name: {payment['customer_name']}
Amount: {payment['currency']} {payment['amount']}
Failure reason: {payment['resolved_failure_code'].replace('_', ' ').lower()}
Recommended action: {payment['recovery_action']}

Respond with ONLY the message text, nothing else."""
