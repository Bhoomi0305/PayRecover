import json
import argparse
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"


def load_executed_payments(filename: str) -> list:
    path = DATA_DIR / filename
    with open(path) as f:
        return json.load(f)


def build_audit_entry(payment: dict) -> dict:
    """
    Turn one fully-processed payment record into a clean, narrative
    audit trail entry - the full story of what happened and why,
    at every stage.
    """
    return {
        "payment_id": payment["payment_id"],
        "customer_name": payment["customer_name"],
        "amount": payment["amount"],
        "currency": payment["currency"],
        "payment_method": payment["payment_method"],
        "failed_at": payment["failed_at"],
        "stage_1_original_failure": {
            "reported_code": payment["failure_code"],
            "raw_gateway_message": payment["raw_gateway_message"],
        },
        "stage_2_classification": {
            "resolved_code": payment["resolved_failure_code"],
            "method": payment["classification_method"],
            "confidence": payment["classification_confidence"],
            "reasoning": payment["classification_reasoning"],
        },
        "stage_3_recovery_decision": {
            "action": payment["recovery_action"],
            "reasoning": payment["recovery_reasoning"],
        },
        "stage_4_execution": {
            "outcome": payment["execution_outcome"],
            "final_status": payment["status"],
            "retry_count": payment["retry_count"],
            "executed_at": payment["executed_at"],
        },
        "narrative": build_narrative(payment),
    }


def build_narrative(payment: dict) -> str:
    """One human-readable sentence summarizing the whole journey - this
    is what you'd actually show a judge or put in a UI, rather than
    making them read four nested JSON blocks."""
    return (
        f"Payment of {payment['currency']} {payment['amount']} via "
        f"{payment['payment_method']} failed ({payment['raw_gateway_message']}). "
        f"Classified as {payment['resolved_failure_code']} via "
        f"{payment['classification_method']} "
        f"(confidence {payment['classification_confidence']}). "
        f"Decision: {payment['recovery_action']} - {payment['recovery_reasoning']} "
        f"Outcome: {payment['execution_outcome']}, final status "
        f"{payment['status']}."
    )


def build_metrics_report(payments: list) -> dict:
    total = len(payments)

    status_counts = {}
    for p in payments:
        status = p["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    recovered = [p for p in payments if p["status"] == "RECOVERED"]
    total_failed_value = sum(p["amount"] for p in payments)
    total_recovered_value = sum(p["amount"] for p in recovered)

    rule_based = [p for p in payments if p["classification_method"] == "RULE_BASED"]
    llm_classified = [p for p in payments if p["classification_method"] == "LLM"]
    llm_failed = [
        p
        for p in payments
        if p["classification_method"]
        in ("LLM_API_ERROR_FALLBACK", "LLM_FAILED_FALLBACK")
    ]

    return {
        "generated_at": datetime.now().isoformat(),
        "total_payments_processed": total,
        "total_failed_value": round(total_failed_value, 2),
        "total_recovered_value": round(total_recovered_value, 2),
        "recovery_rate_pct": round((len(recovered) / total) * 100, 1) if total else 0,
        "status_breakdown": status_counts,
        "classification_breakdown": {
            "RULE_BASED": len(rule_based),
            "LLM": len(llm_classified),
            "LLM_FALLBACK": len(llm_failed),
        },
    }


def save_json(data, filename: str):
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved -> {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Assemble audit trail and metrics report"
    )
    parser.add_argument("--dataset", choices=["dev", "full"], default="dev")
    args = parser.parse_args()

    input_file = f"executed_payments_{args.dataset}.json"
    payments = load_executed_payments(input_file)
    print(f"Loaded {len(payments)} executed payments from {input_file}\n")

    audit_entries = [build_audit_entry(p) for p in payments]
    save_json(audit_entries, f"audit_trail_{args.dataset}.json")

    metrics = build_metrics_report(payments)
    save_json(metrics, f"metrics_{args.dataset}.json")

    print("\n--- Metrics Report ---")
    print(f"Total processed: {metrics['total_payments_processed']}")
    print(f"Recovery rate: {metrics['recovery_rate_pct']}%")
    print(f"Total recovered value: Rs.{metrics['total_recovered_value']}")
    print(f"Total failed value (before recovery): Rs.{metrics['total_failed_value']}")
    print("\nStatus breakdown:")
    for status, count in metrics["status_breakdown"].items():
        print(f"  {status}: {count}")
    print("\nClassification breakdown:")
    for method, count in metrics["classification_breakdown"].items():
        print(f"  {method}: {count}")

    print("\n--- Sample narrative (first entry) ---")
    print(audit_entries[0]["narrative"])
