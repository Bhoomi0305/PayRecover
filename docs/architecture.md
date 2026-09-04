# PayRecover — Architecture

## Problem

Failed payments are common in any payments system — insufficient funds, bank
timeouts, OTP failures, risk blocks, and more. Today, recovering these
failures typically means manual review or blunt retry logic with no
understanding of _why_ a payment failed. PayRecover is an agent pipeline that
detects a failed payment, diagnoses its root cause, decides an appropriate
recovery action within safety bounds, executes that action, and produces a
full audit trail of what happened and why.

## Pipeline overview

                    Failed Payment
                         │
                         ▼

┌────────────────────────────────────────────────┐
│ Classification │
| Rule-based lookup for clean failure codes; │
│ LLM (Gemini 3.5 Flash-Lite) for ambiguous │
│ raw gateway messages |
└────────────────────────┬───────────────────────┘
▼
┌─────────────────────────────────────────────────────┐
│ Recovery Decision │
| Guardrailed decision: retry cap, confidence |
│ floor, non-recoverable check, high-value │
│ caution, then taxonomy-driven default strategy |
└────────────────────────┬────────────────────────────┘
▼
┌─────────────────────────────────────────────────┐
│ Execution │
| Simulates carrying out the decided action │
│ (retry, notify, escalate); |
| updates status |
└────────────────────────┬────────────────────────┘
▼
Loop back to Recovery Decision if not yet terminal
(bounded by MAX_RETRIES=3, safety cap of 5 iterations)
│
▼
┌─────────────────────────────────────────────────┐
│ Audit Trail │
| Assembles all four stages + a plain-language │
│ narrative per payment, plus aggregate metrics |
└─────────────────────────────────────────────────┘

Each stage is a separate, independently testable module
(`classifier.py`, `recovery.py`, `execution.py`, `recovery_loop.py`,
`audit_trail.py`), each with a batch runner that processes the full
dataset and prints a summary. This separation let each stage be built,
tested, and debugged in isolation before being wired into the full loop.

## Why AI is used only where it's needed

Roughly two-thirds of failure codes arrive from the gateway already
categorized (e.g. a clean `NETWORK_ERROR` code). These are resolved via
fast, free, deterministic rule-based lookup — no LLM call, no latency, no
cost, fully explainable.

The remaining third arrive only as raw, unstructured bank/gateway text
(e.g. _"Txn declined by issuing bank. RC: 51"_). These genuinely require
language understanding to classify, so they're routed to an LLM
(Gemini 3.5 Flash-Lite), prompted to return structured JSON with a
resolved code, confidence score, and one-line reasoning.

This hybrid design is a deliberate choice, not a fallback: **AI is used
precisely where deterministic logic can't do the job, not as a blanket
approach.** In the final full run (150 payments), 67.3% resolved via
rules and 32.7% via LLM.

## Guardrails

The recovery decision agent enforces four checks, in this priority order,
before consulting the taxonomy's default strategy:

1. **Retry cap** — a payment that's already been attempted `MAX_RETRIES`
   (3) times stops automated recovery entirely.
2. **Confidence floor** — if the classifier's confidence is below `0.6`,
   the payment is escalated to a human rather than acted on.
3. **Non-recoverable failure types** — failures the taxonomy marks as
   `recoverable: False` are never auto-retried. Customer-fixable ones
   (e.g. invalid card details) get a notify action; everything else
   (e.g. risk-engine blocks) is escalated.
4. **High-value caution** — payments above ₹10,000 are escalated for
   human review regardless of failure type, since the cost of a wrong
   automated action scales with transaction size.

Guardrails are checked in this specific order — most restrictive first —
so a high-risk case can never slip through to "normal" handling by
accident. This ordering is enforced in code, not left to a prompt.

Every stage in the pipeline follows the same underlying principle:
**unknown or uncertain → escalate to a human, never guess.** This applies
to malformed LLM output, unrecognized failure codes, and unrecognized
recovery actions alike — three separate defensive checks, one consistent
philosophy.

## The recovery loop

A single decision-and-execute pass isn't enough to reflect real recovery
behavior — a payment might need multiple attempts before succeeding or
being correctly identified as unrecoverable. `recovery_loop.py`
repeatedly runs decide → execute → re-evaluate for each payment, feeding
the updated retry count back into the guardrails on each pass, until it
reaches a genuine terminal state (`RECOVERED`, `ESCALATED`,
`PENDING_CUSTOMER_ACTION`, or `UNRECOVERABLE`). A hard iteration cap (5)
exists independently of `MAX_RETRIES` as defense-in-depth, in case the
retry-cap guardrail itself ever had a bug. In the final run, payments
needed an average of 1.45 attempts before reaching a terminal state.

## Data

All data is synthetically generated (`generate_data.py`), seeded for
reproducibility. Payment amounts follow a triangular distribution
(mode ₹800, range ₹199–₹15,000) to approximate realistic transaction
volume patterns rather than a flat/uniform spread. 35% of records are
deliberately generated with only a messy raw gateway message (no clean
code), to ensure the LLM classification path is genuinely exercised
rather than a rarely-used edge case.

## Known limitations

**LLM confidence calibration.** The classifier's LLM-reported confidence
scores are consistently high (0.85–1.0) regardless of how genuinely
ambiguous the input message is. This is a known, general limitation of
self-reported LLM confidence — it reflects the model's tendency to
express certainty in its output format, not a calibrated measure of
actual accuracy. As a result, the confidence-floor guardrail rarely
triggers on this dataset. In a production system, this would be replaced
with a better-calibrated signal (e.g. output log-probabilities or an
ensemble/self-consistency check across multiple calls) rather than a
model's self-reported number.

**Simulated execution outcomes.** Since this system doesn't have access
to real bank rails, execution success/failure is simulated using
assumed probabilities per action type (e.g. immediate retries succeed
more often than asking a customer to try an entirely new payment
method). These are reasonable, documented assumptions, not measured
real-world rates.

**Provider-agnostic design.** The classifier's LLM integration was built
against OpenAI initially and switched to Gemini mid-build with changes
isolated to `config.py` and the API-calling portion of `classifier.py`
— the decision logic, execution, and audit trail layers required no
changes, since the classifier's output contract (`resolved_code`,
`method`, `confidence`, `reasoning`) is the same regardless of provider.

## Results (full 150-payment run)

┌──────────────────────────────────────────────────┐
| Metric | Value |
|-----------------------------------|--------------|
| Payments processed | 150 |
| Recovery rate | 63.3% |
| Total recovered value | ₹4,15,791.45 |
| Total failed value (pre-recovery) | ₹7,97,155.80 |
| Resolved via rules | 67.3% |
| Resolved via LLM | 32.7% |
| Escalated to human | 27.3% |
| Average attempts per payment | 1.45 |
└──────────────────────────────────────────────────┘

## Tech stack

Python, FastAPI, Gemini API (3.5 Flash-Lite), HTML/CSS/JS (vanilla, no framework or build step).
