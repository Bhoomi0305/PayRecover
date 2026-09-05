import hmac
import hashlib
import json
import requests

from backend.config import RAZORPAY_WEBHOOK_SECRET

payload = {
    "event": "payment.failed",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_test_manual_001",
                "email": "test@example.com",
                "amount": 50000,  # in paise = INR 500
                "currency": "INR",
                "method": "upi",
                "error_description": "Network connection timed out during payment processing",
            }
        }
    },
}

body = json.dumps(payload).encode()
signature = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()

response = requests.post(
    "http://127.0.0.1:8000/api/webhooks/razorpay",
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature,
    },
)
print(response.status_code, response.json())
