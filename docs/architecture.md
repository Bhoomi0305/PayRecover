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

## Agent architecture

The system uses three LLM-capable agents, with a deterministic
guardrail-based decision layer between the first two:

1. **Classification Agent** (LLM-capable) — resolves the root cause of
   a payment failure. Clean failure codes are resolved via fast,
   free, deterministic rule-based lookup. Ambiguous raw gateway
   messages are classified by an LLM (Gemini 3.5 Flash-Lite),
   constrained to only the failure codes plausible for that payment's
   method.

2. **Recovery Decision layer** (deterministic, not LLM-based) —
   proposes a recovery action by applying explicit guardrails in
   priority order: retry cap, confidence floor, non-recoverable
   failure check, high-value caution, then a taxonomy-driven default
   strategy. This step is intentionally rule-based rather than
   LLM-driven, keeping the core money-moving decision fast, free of
   API cost, and fully explainable/auditable on its own.

3. **Compliance Reviewer Agent** (LLM-capable) — independently reviews
   any proposed action that would actually retry or redirect a
   payment, with the authority to override toward escalation. Only
   money-touching actions are reviewed; decisions that already
   resulted in escalation or notification are already conservative
   and pass through unreviewed. If the reviewer is unavailable or
   fails to respond, the system defaults to escalation rather than
   proceeding unreviewed - consistent with the "uncertain → human"
   principle applied throughout the pipeline.

4. **Notification Agent** (LLM-capable) — drafts the customer-facing
   message for any payment where a customer notification was part of
   the recovery path, whether or not that payment ultimately
   recovered. Runs as a post-processing step over the finalized audit
   trail and does not influence any recovery decision or metric - its
   fallback (a plain template) reflects that this is content
   generation, not a risk-bearing decision.

This design deliberately reserves LLM reasoning for the tasks that
genuinely need language understanding or independent judgment
(ambiguous classification, compliance review, message drafting),
while keeping the actual recovery decision - the step with direct
financial consequence - as fast, deterministic, guardrailed logic
rather than an LLM call. This is a design choice, not a limitation:
it makes the highest-stakes decision in the system the most
predictable and auditable one.

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

**Classification consistency.** Repeated classification of identical
ambiguous messages (temperature=0) was tested across multiple runs.
Most messages classified consistently every time, but occasional
run-to-run variation was observed on a small subset (roughly 1 in 8
messages, varying which message each time) — a known characteristic of
hosted LLM inference even at temperature=0, not a bug in the
classification logic. This reinforces the design decision to route
low-confidence or inherently ambiguous cases toward human escalation
rather than fully trusting a single automated classification.

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

**Payment-method-aware classification.** Early iterations allowed the
classifier to assign failure codes inconsistent with the payment
method (e.g. a card-specific decline on a wallet payment). This was
caught via the Compliance Reviewer Agent flagging the mismatch, and
fixed by constraining both synthetic data generation and LLM
classification to method-plausible failure codes only, with an
explicit fallback if the model returns an incompatible code anyway.
This was a genuine bug the two-agent review surfaced during
development, not a hypothetical.

## Results (full 150-payment run)

| Metric                               | Value        |
| ------------------------------------ | ------------ |
| Payments processed                   | 150          |
| Recovery rate                        | 61.3%        |
| Total recovered value                | ₹4,16,647.79 |
| Total failed value (pre-recovery)    | ₹7,94,151.70 |
| Resolved via rules                   | 68.7%        |
| Resolved via LLM                     | 31.3%        |
| Escalated to human/compliance review | 31.3%        |
| Average attempts per payment         | 1.45         |

## Tech stack

Python, FastAPI, Gemini API (3.5 Flash-Lite), HTML/CSS/JS (vanilla, no framework or build step).
