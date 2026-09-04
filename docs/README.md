# PayRecover

An AI agent pipeline that detects, diagnoses, and recovers failed payment
transactions — built for the Razorpay AI Buildathon (AI Revenue Recovery
track).

## What it does

When a payment fails, PayRecover:

1. **Classifies** the root cause — via fast rule-based lookup for
   clean, payment-method-compatible failure codes, or an LLM
   (constrained to method-plausible outcomes) for ambiguous raw
   gateway messages
2. **Decides** a recovery action using deterministic guardrails —
   retry limits, confidence thresholds, non-recoverable-failure
   checks, and high-value caution
3. **Reviews** the proposed action with an independent Compliance
   Reviewer Agent, which can override to escalation before anything
   executes
4. **Executes** the approved action (simulated) and re-evaluates if
   not yet resolved, looping within bounds
5. **Logs** everything to a full audit trail with a plain-language
   narrative per payment
6. **Notifies** the customer, where applicable, via a drafted
   message generated after the outcome is final

See [`docs/architecture.md`](docs/architecture.md) for the full design,
guardrails, and known limitations.

## Results (150 synthetic failed payments)

| Metric                               | Value        |
| ------------------------------------ | ------------ |
| Recovery rate                        | 61.3%        |
| Total recovered value                | ₹4,16,647.79 |
| Total failed value (pre-recovery)    | ₹7,94,151.70 |
| Resolved via rules (no API cost)     | 68.7%        |
| Resolved via LLM                     | 31.3%        |
| Escalated to human/compliance review | 31.3%        |
| Average attempts per payment         | 1.45         |

## Tech stack

Python · FastAPI · Gemini API (3.5 Flash-Lite) · HTML/CSS/JS

## Project structure

```
└── 📁payrecover
    └── 📁.vscode
        ├── settings.json
    └── 📁backend
        └── 📁agents
            ├── audit_trail.py
            ├── batch_classify.py
            ├── batch_notify.py
            ├── batch_recovery_loop.py
            ├── classifier.py
            ├── execution.py
            ├── notifier.py
            ├── recovery_loop.py
            ├── recovery.py
            ├── reviewer.py
        └── 📁data
            ├── audit_trail_full.json
            ├── classified_payments_full.json
            ├── executed_payments_full.json
            ├── failed_payments_full.json
            ├── failure_taxonomy.py
            ├── generate_data.py
            ├── metrics_full.json
            ├── recovery_decisions_full.json
        ├── config.py
        ├── main.py
    └── 📁docs
        ├── architecture.md
        ├── README.md
    └── 📁frontend
        ├── app.js
        ├── index.html
        ├── style.css
    ├── .gitignore
    └── requirements.txt
```

## Setup

1. Clone the repo and create a virtual environment:
   python3 -m venv venv
   source venv/bin/activate # Windows: venv\Scripts\Activate.ps1
   pip install -r requirements.txt

2. Create a `.env` file in the project root:
   GEMINI_API_KEY=your_key_here
   USE_MOCK_LLM=false
   Set `USE_MOCK_LLM=true` to run the full pipeline without a real API
   key or cost — the LLM classification step will return simulated
   results, clearly tagged `LLM_MOCK` in the output so they're never
   confused with real results.

3. Run the pipeline, in order:
   python3 -m backend.data.generate_data
   python3 -m backend.agents.batch_classify --dataset full
   python3 -m backend.agents.batch_recovery_loop --dataset full
   python3 -m backend.agents.audit_trail --dataset full
   python3 -m backend.agents.batch_notify --dataset full
4. Start the server and view the dashboard:
   uvicorn backend.main:app --reload
   Open `http://127.0.0.1:8000`

## API endpoints

| Endpoint                             | Description                       |
| ------------------------------------ | --------------------------------- |
| `GET /api/metrics`                   | Aggregate recovery metrics        |
| `GET /api/payments`                  | Full audit trail for all payments |
| `GET /api/payments?status=escalated` | Filter by final status            |
| `GET /api/payments/{payment_id}`     | Single payment's full audit entry |

## Notes on synthetic data

All payment data is synthetically generated and seeded for
reproducibility (`random.seed(42)`). Amounts follow a triangular
distribution to approximate realistic transaction volume rather than a
flat spread. See `docs/architecture.md` for the full reasoning behind
data design choices and known limitations (LLM confidence calibration,
simulated execution rates).
