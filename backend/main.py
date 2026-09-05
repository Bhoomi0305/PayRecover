import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# imports for Razorpay integration
import razorpay
from fastapi import Request, HTTPException
from datetime import datetime
from backend.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET
from backend.agents.classifier import classify_payment
from backend.agents.recovery_loop import run_recovery_loop
from backend.agents.audit_trail import build_audit_entry

app = FastAPI(title="PayRecover")

DATA_DIR = Path(__file__).parent / "data"

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse("frontend/index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "PayRecover backend is running"}


def load_json(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found - run the pipeline scripts first",
        )
    with open(path) as f:
        return json.load(f)


@app.get("/api/metrics")
def get_metrics():
    return load_json("metrics_full.json")


@app.get("/api/payments")
def get_payments(status: str | None = None):
    payments = load_json("audit_trail_full.json")
    if status:
        payments = [
            p
            for p in payments
            if p["stage_4_execution"]["final_status"].lower() == status.lower()
        ]
    return payments


@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str):
    payments = load_json("audit_trail_full.json")
    match = next((p for p in payments if p["payment_id"] == payment_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    return match


# Razorpay integration
razorpay_client = (
    razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    if RAZORPAY_KEY_ID
    else None
)

LIVE_EVENTS_FILE = DATA_DIR / "live_webhook_events.json"


def razorpay_payload_to_payment(payload: dict) -> dict:
    """Map a Razorpay payment.failed webhook payload into our internal
    payment shape, so it can run through the exact same pipeline as
    our synthetic data."""
    entity = payload["payload"]["payment"]["entity"]
    error_desc = entity.get("error_description") or "Unknown gateway error"

    return {
        "payment_id": entity["id"],
        "customer_name": entity.get("email", "unknown"),
        "amount": entity["amount"] / 100,  # Razorpay sends amount in paise
        "currency": entity.get("currency", "INR"),
        "payment_method": entity.get("method", "unknown"),
        "failed_at": datetime.now().isoformat(),
        "failure_code": "AMBIGUOUS",  # always route real gateway text through the classifier
        "raw_gateway_message": error_desc,
        "retry_count": 0,
        "status": "FAILED",
    }


@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not razorpay_client:
        raise HTTPException(
            status_code=500, detail="Razorpay credentials not configured"
        )

    try:
        razorpay_client.utility.verify_webhook_signature(
            raw_body.decode(), signature, RAZORPAY_WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(raw_body)

    if payload.get("event") != "payment.failed":
        return {"status": "ignored", "reason": "not a payment.failed event"}

    payment = razorpay_payload_to_payment(payload)

    classification = classify_payment(payment)
    payment.update(
        {
            "resolved_failure_code": classification["resolved_code"],
            "classification_method": classification["method"],
            "classification_confidence": classification["confidence"],
            "classification_reasoning": classification["reasoning"],
        }
    )

    final = run_recovery_loop(payment)
    audit_entry = build_audit_entry(final)
    audit_entry["source"] = "LIVE_RAZORPAY_WEBHOOK"

    existing = []
    if LIVE_EVENTS_FILE.exists():
        with open(LIVE_EVENTS_FILE) as f:
            existing = json.load(f)
    existing.append(audit_entry)
    with open(LIVE_EVENTS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    return {
        "status": "processed",
        "payment_id": payment["payment_id"],
        "outcome": final["status"],
    }


@app.get("/api/live-events")
def get_live_events():
    if not LIVE_EVENTS_FILE.exists():
        return []
    with open(LIVE_EVENTS_FILE) as f:
        return json.load(f)
