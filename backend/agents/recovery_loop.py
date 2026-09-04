import time
from datetime import datetime
from backend.agents.recovery import decide_recovery_action
from backend.agents.execution import execute_recovery, NO_RETRY_ACTIONS
from backend.agents.reviewer import review_decision, REVIEWABLE_ACTIONS
from backend.config import USE_MOCK_LLM

# Actions that don't attempt execution at all - reaching one of these
# ends the loop immediately, no further attempts possible
TERMINAL_NO_EXECUTION = set(NO_RETRY_ACTIONS.keys())


def run_recovery_loop(payment: dict, max_iterations: int = 5) -> dict:
    """
    Repeatedly decide + execute for a single payment until it reaches
    a terminal state: RECOVERED, or a decision that doesn't retry
    (ESCALATE_HUMAN, NOTIFY_CUSTOMER_ONLY, NO_ACTION_MAX_RETRIES).

    max_iterations is a hard safety cap independent of MAX_RETRIES -
    protects against any future guardrail bug causing an infinite loop.
    """
    current = dict(payment)  # work on a copy, don't mutate the original
    attempts = []

    for _ in range(max_iterations):
        decision = decide_recovery_action(current)

        review = review_decision(current, decision)
        if decision["action"] in REVIEWABLE_ACTIONS and not USE_MOCK_LLM:
            time.sleep(2)  # pace real reviewer API calls

        current["recovery_action"] = review["final_action"]
        current["recovery_reasoning"] = decision["reasoning"]
        current["review_reasoning"] = review["review_reasoning"]
        current["review_approved"] = review["approved"]

        if current["recovery_action"] in TERMINAL_NO_EXECUTION:
            final_status = NO_RETRY_ACTIONS[current["recovery_action"]]
            current["status"] = final_status
            current["execution_outcome"] = "NO_AUTOMATED_ACTION"
            current["executed_at"] = datetime.now().isoformat()

            attempts.append(
                {
                    "action": current["recovery_action"],
                    "reasoning": decision["reasoning"],
                    "review": review["review_reasoning"],
                    "outcome": "NO_ATTEMPT_MADE",
                }
            )
            break

        outcome = execute_recovery(current)
        current.update(outcome)

        attempts.append(
            {
                "action": current["recovery_action"],
                "reasoning": decision["reasoning"],
                "review": review["review_reasoning"],
                "outcome": outcome["execution_outcome"],
                "retry_count_after": outcome["retry_count"],
            }
        )

        if current["status"] == "RECOVERED":
            break
        # else: loop again - next decide_recovery_action call will see
        # the updated retry_count and re-check all guardrails fresh

    current["attempt_history"] = attempts
    return current
