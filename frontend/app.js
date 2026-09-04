const API = "/api";

async function init() {
  const [metrics, payments] = await Promise.all([
    fetch(`${API}/metrics`).then(r => r.json()),
    fetch(`${API}/payments`).then(r => r.json()),
  ]);

  renderMetrics(metrics);
  renderFilterBar(metrics, payments);
  renderLedger(payments);
}

function renderMetrics(metrics) {
  document.getElementById("generatedAt").textContent =
    `Generated ${new Date(metrics.generated_at).toLocaleString()}`;

  const band = document.getElementById("metricsBand");
  band.innerHTML = `
    <div class="metric">
      <span class="metric-value">${metrics.recovery_rate_pct}%</span>
      <span class="metric-label">Recovery rate</span>
    </div>
    <div class="metric">
      <span class="metric-value">₹${formatNumber(metrics.total_recovered_value)}</span>
      <span class="metric-label">Recovered value</span>
    </div>
    <div class="metric">
      <span class="metric-value">₹${formatNumber(metrics.total_failed_value)}</span>
      <span class="metric-label">Total failed value</span>
    </div>
    <div class="metric">
      <span class="metric-value">${metrics.total_payments_processed}</span>
      <span class="metric-label">Payments processed</span>
    </div>
  `;
}

function renderFilterBar(metrics, allPayments) {
  const statuses = ["all", ...Object.keys(metrics.status_breakdown)];
  const bar = document.getElementById("filterBar");

  bar.innerHTML = statuses.map(status => {
    const count = status === "all"
      ? allPayments.length
      : metrics.status_breakdown[status];
    const label = status === "all" ? "All" : toTitleCase(status);
    return `<button class="filter-btn" data-status="${status}">${label} (${count})</button>`;
  }).join("");

  bar.querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      bar.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const status = btn.dataset.status;
      const filtered = status === "all"
        ? allPayments
        : allPayments.filter(p => p.stage_4_execution.final_status.toLowerCase() === status.toLowerCase());
      renderLedger(filtered);
    });
  });

  bar.querySelector('[data-status="all"]').classList.add("active");
}


function renderLedger(payments) {
  const ledger = document.getElementById("ledger");

  if (payments.length === 0) {
    ledger.innerHTML = `<div class="ledger-empty">No payments match this filter.</div>`;
    return;
  }

  ledger.innerHTML = payments.map(p => {
    const status = p.stage_4_execution.final_status;
    const methodLabel = METHOD_LABELS[p.stage_2_classification.method] || humanize(p.stage_2_classification.method);
    const showConfidence = p.stage_2_classification.method !== "RULE_BASED";
    const confidenceText = showConfidence
      ? " · " + Math.round(p.stage_2_classification.confidence * 100) + "% confidence"
      : "";
    const actionIcon = ACTION_ICONS[p.stage_3_recovery_decision.action] || "•";
    const outcomeIcon = status === "RECOVERED" ? "✓" : "◈";
    const attemptWord = p.stage_4_execution.retry_count === 1 ? "attempt" : "attempts";

    return `
      <div class="ledger-row" data-id="${p.payment_id}">
        <div class="ledger-row-header" tabindex="0" role="button" aria-expanded="false">
          <span class="payment-id">${p.payment_id}</span>
          <span class="amount">₹${formatNumber(p.amount)}</span>
          <span class="method">${p.payment_method}</span>
          <span class="status-tag status-${status.toLowerCase()}">${toTitleCase(status)}</span>
          <span class="chevron">▸</span>
        </div>
        <div class="ledger-detail">
          <div class="flow">
            <div class="flow-step">
              <div class="flow-icon">✕</div>
              <div class="flow-content">
                <div class="flow-title">Failed</div>
                <div class="flow-body">${humanize(p.stage_1_original_failure.reported_code)}</div>
              </div>
            </div>
            <div class="flow-connector"></div>
            <div class="flow-step">
              <div class="flow-icon">◎</div>
              <div class="flow-content">
                <div class="flow-title">Diagnosed as ${humanize(p.stage_2_classification.resolved_code)}</div>
                <div class="flow-body">${methodLabel}${confidenceText}</div>
              </div>
            </div>
            <div class="flow-connector"></div>
            <div class="flow-step">
              <div class="flow-icon">${actionIcon}</div>
              <div class="flow-content">
                <div class="flow-title">${humanize(p.stage_3_recovery_decision.action)}</div>
                <div class="flow-body">${p.stage_3_recovery_decision.reasoning}</div>
              </div>
            </div>
            <div class="flow-connector"></div>
            <div class="flow-step">
              <div class="flow-icon">${outcomeIcon}</div>
              <div class="flow-content">
                <div class="flow-title">${humanize(status)}</div>
                <div class="flow-body">${p.stage_4_execution.retry_count} ${attemptWord}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");

  ledger.querySelectorAll(".ledger-row-header").forEach(header => {
    const toggle = () => {
      const row = header.closest(".ledger-row");
      const isExpanded = row.classList.toggle("expanded");
      header.setAttribute("aria-expanded", isExpanded);
    };
    header.addEventListener("click", toggle);
    header.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
    });
  });
}

function formatNumber(n) {
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function toTitleCase(s) {
  return s.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

init();

function humanize(s) {
  if (!s) return "";
  return s.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

const METHOD_LABELS = {
  RULE_BASED: "Rule-based lookup",
  LLM: "AI classification",
  LLM_MOCK: "AI classification (simulated)",
};

const ACTION_ICONS = {
  IMMEDIATE_RETRY: "↻",
  DELAYED_RETRY: "↻",
  NOTIFY_AND_RETRY: "↻",
  SUGGEST_ALT_METHOD: "⇄",
  NOTIFY_CUSTOMER_ONLY: "✉",
  ESCALATE_HUMAN: "⚑",
  NO_ACTION_MAX_RETRIES: "⏹",
};