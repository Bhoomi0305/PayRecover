import json
import random
import uuid
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from backend.data.failure_taxonomy import (
    FAILURE_TAXONOMY,
    AMBIGUOUS_RAW_MESSAGES,
    METHOD_COMPATIBLE_CODES,
)

random.seed(42)

CLEAN_FAILURE_CODES = [code for code in FAILURE_TAXONOMY if code != "AMBIGUOUS"]

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
CUSTOMER_NAMES = [
    "Aarav Sharma",
    "Priya Patel",
    "Rohan Mehta",
    "Ananya Iyer",
    "Vikram Singh",
    "Sneha Reddy",
    "Karan Kapoor",
    "Ishita Joshi",
    "Arjun Nair",
    "Divya Rao",
]


def random_timestamp(days_back=14):
    now = datetime.now()
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return (now - delta).isoformat()


def generate_payment():
    payment_method = random.choice(PAYMENT_METHODS)
    is_ambiguous = random.random() < 0.35

    if is_ambiguous:
        failure_code = "AMBIGUOUS"
        raw_message = random.choice(AMBIGUOUS_RAW_MESSAGES)
    else:
        compatible_codes = METHOD_COMPATIBLE_CODES[payment_method]
        failure_code = random.choice(compatible_codes)
        raw_message = FAILURE_TAXONOMY[failure_code]["description"]

    return {
        "payment_id": f"pay_{uuid.uuid4().hex[:12]}",
        "customer_name": random.choice(CUSTOMER_NAMES),
        "amount": round(random.triangular(199, 15000, 800), 2),
        "currency": "INR",
        "payment_method": payment_method,
        "failed_at": random_timestamp(),
        "failure_code": failure_code,
        "raw_gateway_message": raw_message,
        "retry_count": 0,
        "status": "FAILED",
    }


def generate_dataset(n):
    return [generate_payment() for _ in range(n)]


def save_dataset(dataset, filename):
    output_path = Path(__file__).parent / filename
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"Generated {len(dataset)} records -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic failed payment data"
    )
    parser.add_argument(
        "--n", type=int, default=None, help="Custom size; skips dev/full generation"
    )
    args = parser.parse_args()

    if args.n:
        # one-off custom size, e.g. python3 -m backend.data.generate_data --n 30
        save_dataset(generate_dataset(args.n), "failed_payments_custom.json")
    else:
        # default: generate both dev (fast iteration) and full (demo) sets
        save_dataset(generate_dataset(20), "failed_payments_dev.json")
        save_dataset(generate_dataset(150), "failed_payments_full.json")
