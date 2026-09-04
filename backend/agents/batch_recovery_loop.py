import json
import argparse
from pathlib import Path

from backend.agents.recovery_loop import run_recovery_loop

DATA_DIR = Path(__file__).parent.parent / "data"


def load_classified_payments(filename: str) -> list:
    path = DATA_DIR / filename
    with open(path) as f:
        return json.load(f)


def run_batch(payments: list) -> list:
    results = []
    for i, payment in enumerate(payments, start=1):
        final = run_recovery_loop(payment)
        results.append(final)

        n_attempts = len(final["attempt_history"])
        print(
            f"[{i}/{len(payments)}] {payment['payment_id']} -> "
            f"{final['status']} after {n_attempts} attempt(s)"
        )

    return results


def save_results(results: list, filename: str):
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved -> {path}")


def summarize(results: list) -> dict:
    summary = {"total": len(results), "by_status": {}, "avg_attempts": 0}
    total_attempts = 0
    total_recovered_amount = 0.0

    for r in results:
        status = r["status"]
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        total_attempts += len(r["attempt_history"])
        if status == "RECOVERED":
            total_recovered_amount += r["amount"]

    summary["avg_attempts"] = round(total_attempts / len(results), 2) if results else 0
    summary["total_recovered_amount"] = round(total_recovered_amount, 2)
    recovered_count = summary["by_status"].get("RECOVERED", 0)
    summary["recovery_rate_pct"] = round((recovered_count / summary["total"]) * 100, 1)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run recovery+execution loop until terminal state"
    )
    parser.add_argument("--dataset", choices=["dev", "full"], default="dev")
    args = parser.parse_args()

    input_file = f"classified_payments_{args.dataset}.json"
    output_file = f"executed_payments_{args.dataset}.json"

    payments = load_classified_payments(input_file)
    print(f"Loaded {len(payments)} classified payments from {input_file}\n")

    results = run_batch(payments)
    save_results(results, output_file)

    summary = summarize(results)
    print("\n--- Summary ---")
    print(f"Total processed: {summary['total']}")
    print(f"Recovery rate: {summary['recovery_rate_pct']}%")
    print(f"Total recovered amount: Rs.{summary['total_recovered_amount']}")
    print(f"Average attempts per payment: {summary['avg_attempts']}")
    for status, count in summary["by_status"].items():
        pct = round((count / summary["total"]) * 100, 1)
        print(f"  {status}: {count} ({pct}%)")
