import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
