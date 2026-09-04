import json
import argparse
from pathlib import Path

from backend.agents.notifier import needs_notification, generate_notification

DATA_DIR = Path(__file__).parent.parent / "data"


def load_audit_trail(filename: str) -> list:
    path = DATA_DIR / filename
    with open(path) as f:
        return json.load(f)


def run_batch_notify(entries: list) -> list:
    notified_count = 0
    for entry in entries:
        payment_like = {
            "payment_id": entry["payment_id"],
            "customer_name": entry["customer_name"],
            "amount": entry["amount"],
            "currency": entry["currency"],
            "resolved_failure_code": entry["stage_2_classification"]["resolved_code"],
            "recovery_action": entry["stage_3_recovery_decision"]["action"],
            "status": entry["stage_4_execution"]["final_status"],
        }

        if needs_notification(payment_like):
            result = generate_notification(payment_like)
            entry["customer_notification"] = result
            notified_count += 1
        else:
            entry["customer_notification"] = None

    print(
        f"Generated {notified_count} customer notifications out of {len(entries)} payments"
    )
    return entries


def save_results(entries: list, filename: str):
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"Saved -> {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add customer notification drafts to audit trail"
    )
    parser.add_argument("--dataset", choices=["dev", "full"], default="dev")
    args = parser.parse_args()

    input_file = f"audit_trail_{args.dataset}.json"
    entries = load_audit_trail(input_file)
    print(f"Loaded {len(entries)} audit entries from {input_file}\n")

    entries = run_batch_notify(entries)
    save_results(
        entries, input_file
    )  # overwrites audit_trail file, adding the new field
