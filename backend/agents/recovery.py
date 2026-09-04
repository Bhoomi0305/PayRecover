# backend/agents/recovery.py

from backend.data.failure_taxonomy import FAILURE_TAXONOMY

MAX_RETRIES = 3
HIGH_VALUE_THRESHOLD = 10000
MIN_CONFIDENCE = 0.6

# Failure codes where, even if "recoverable", NOTIFY (not escalate) is the
# more appropriate non-retry action - i.e. the customer needs to fix something,
# not a human agent.
CUSTOMER_FIXABLE_CODES = {"INVALID_CARD_DETAILS"}


def decide_recovery_action(payment: dict) -> dict:
    """
    Given an already-classified payment, decide what recovery action to take.
    Returns a dict with the decision + human-readable reasoning, so every
    decision is auditable.
    """
    retry_count = payment["retry_count"]
    confidence = payment["classification_confidence"]
    resolved_code = payment["resolved_failure_code"]
    amount = payment["amount"]

    # Guardrail 1: hard retry cap
    if retry_count >= MAX_RETRIES:
        return _decision(
            "NO_ACTION_MAX_RETRIES",
            f"Already attempted {retry_count} times (max {MAX_RETRIES}). Stopping automated recovery.",
        )

    # Guardrail 2: low confidence classification
    if confidence < MIN_CONFIDENCE:
        return _decision(
            "ESCALATE_HUMAN",
            f"Classification confidence ({confidence}) below threshold ({MIN_CONFIDENCE}). Needs human review.",
        )

    # Guardrail 3: non-recoverable failure types
    taxonomy_entry = FAILURE_TAXONOMY.get(resolved_code)
    if taxonomy_entry is None:
        # Defensive fallback: resolved_code wasn't a known taxonomy key at all
        return _decision(
            "ESCALATE_HUMAN",
            f"Unknown resolved failure code '{resolved_code}'. Escalating for safety.",
        )

    if taxonomy_entry["recoverable"] is False:
        if resolved_code in CUSTOMER_FIXABLE_CODES:
            return _decision(
                "NOTIFY_CUSTOMER_ONLY",
                f"'{resolved_code}' requires the customer to fix something (not auto-recoverable).",
            )
        return _decision(
            "ESCALATE_HUMAN",
            f"'{resolved_code}' is not recoverable and not customer-fixable. Escalating.",
        )

    # Guardrail 4: high-value caution
    if amount > HIGH_VALUE_THRESHOLD:
        return _decision(
            "ESCALATE_HUMAN",
            f"Amount (Rs.{amount}) exceeds high-value threshold (Rs.{HIGH_VALUE_THRESHOLD}). Escalating for caution.",
        )

    # Default: use the taxonomy's default strategy for this failure code
    strategy = taxonomy_entry["default_strategy"]
    return _decision(
        strategy,
        f"Standard strategy for '{resolved_code}' applied.",
    )


def _decision(action: str, reasoning: str) -> dict:
    """Small helper to keep every returned decision in the same shape."""
    return {
        "action": action,
        "reasoning": reasoning,
    }
