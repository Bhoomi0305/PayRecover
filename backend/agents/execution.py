import random as _random
from datetime import datetime

# Simulated success probabilities per action - synthetic assumptions,
# not measured real-world rates. Documented here for transparency.
ACTION_SUCCESS_RATES = {
    "IMMEDIATE_RETRY": 0.65,
    "DELAYED_RETRY": 0.55,
    "NOTIFY_AND_RETRY": 0.50,
    "SUGGEST_ALT_METHOD": 0.45,
}

# Actions that don't attempt automated recovery at all
NO_RETRY_ACTIONS = {
    "NOTIFY_CUSTOMER_ONLY": "PENDING_CUSTOMER_ACTION",
    "ESCALATE_HUMAN": "ESCALATED",
    "NO_ACTION_MAX_RETRIES": "UNRECOVERABLE",
}


def execute_recovery(payment: dict) -> dict:
    """
    Simulate carrying out the decided recovery action.
    Returns the fields that should be updated on the payment record.
    """
    action = payment["recovery_action"]
    executed_at = datetime.now().isoformat()

    if action in NO_RETRY_ACTIONS:
        return {
            "status": NO_RETRY_ACTIONS[action],
            "retry_count": payment["retry_count"],
            "execution_outcome": "NO_AUTOMATED_ACTION",
            "executed_at": executed_at,
        }

    success_rate = ACTION_SUCCESS_RATES.get(action)
    if success_rate is None:
        # Defensive: unrecognized action, don't guess - escalate safely
        return {
            "status": "ESCALATED",
            "retry_count": payment["retry_count"],
            "execution_outcome": f"UNKNOWN_ACTION_{action}",
            "executed_at": executed_at,
        }

    succeeded = _random.random() < success_rate

    if succeeded:
        return {
            "status": "RECOVERED",
            "retry_count": payment["retry_count"] + 1,
            "execution_outcome": "SUCCESS",
            "executed_at": executed_at,
        }
    else:
        return {
            "status": "FAILED",
            "retry_count": payment["retry_count"] + 1,
            "execution_outcome": "FAILED_ATTEMPT",
            "executed_at": executed_at,
        }
