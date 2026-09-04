import json
import argparse
from pathlib import Path
import time

from backend.agents.classifier import classify_payment

DATA_DIR = Path(__file__).parent.parent / "data"


def load_payments(filename: str) -> list:
    path = DATA_DIR / filename
    with open(path) as f:
        return json.load(f)


def run_batch_classification(payments: list) -> list:
    results = []
    for i, payment in enumerate(payments, start=1):
        classification = classify_payment(payment)

        if classification["method"] == "LLM":
            time.sleep(2)  # brief pause between real API calls

        # merge original payment data with its classification result
        enriched = {
            **payment,
            "resolved_failure_code": classification["resolved_code"],
            "classification_method": classification["method"],
            "classification_confidence": classification["confidence"],
            "classification_reasoning": classification["reasoning"],
        }
        results.append(enriched)

        print(
            f"[{i}/{len(payments)}] {payment['payment_id']} -> "
            f"{classification['resolved_code']} ({classification['method']})"
        )

    return results


def summarize(results: list) -> dict:
    summary = {
        "total": len(results),
        "by_method": {},
    }
    for r in results:
        method = r["classification_method"]
        summary["by_method"][method] = summary["by_method"].get(method, 0) + 1
    return summary


def save_results(results: list, filename: str):
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved classified results -> {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch classify failed payments")
    parser.add_argument(
        "--dataset",
        choices=["dev", "full"],
        default="dev",
        help="Which dataset to classify: dev (20 records) or full (150 records)",
    )
    args = parser.parse_args()

    input_file = f"failed_payments_{args.dataset}.json"
    output_file = f"classified_payments_{args.dataset}.json"

    payments = load_payments(input_file)
    print(f"Loaded {len(payments)} payments from {input_file}\n")

    results = run_batch_classification(payments)
    save_results(results, output_file)

    summary = summarize(results)
    print("\n--- Summary ---")
    print(f"Total classified: {summary['total']}")
    for method, count in summary["by_method"].items():
        pct = round((count / summary["total"]) * 100, 1)
        print(f"  {method}: {count} ({pct}%)")
