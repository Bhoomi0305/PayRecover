const API = "/api";

// async function init() {
//   const [metrics, payments] = await Promise.all([
//     fetch(`${API}/metrics`).then(r => r.json()),
//     fetch(`${API}/payments`).then(r => r.json()),
//   ]);

//   renderMetrics(metrics);
//   renderFilterBar(metrics, payments);
//   renderLedger(payments);
// }

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
    const status = p.stage_4_execution?.final_status ?? "UNKNOWN";
    const action = p.stage_3_recovery_decision?.action ?? "UNKNOWN";
    const actionReasoning = p.stage_3_recovery_decision?.reasoning ?? "";
    const resolvedCode = p.stage_2_classification?.resolved_code ?? "UNKNOWN";
    const methodLabel = METHOD_LABELS[p.stage_2_classification?.method] || humanize(p.stage_2_classification?.method ?? "");
    const showConfidence = p.stage_2_classification?.method && p.stage_2_classification.method !== "RULE_BASED";
    const confidenceText = showConfidence
      ? " · " + Math.round((p.stage_2_classification.confidence ?? 0) * 100) + "% confidence"
      : "";
    const actionIcon = ACTION_ICONS[action] || "•";
    const outcomeIcon = status === "RECOVERED" ? "✓" : "◈";
    const retryCount = p.stage_4_execution?.retry_count ?? 0;
    const attemptWord = retryCount === 1 ? "attempt" : "attempts";

    return `
      <div class="ledger-row" data-id="${p.payment_id ?? "unknown"}">
        <div class="ledger-row-header" tabindex="0" role="button" aria-expanded="false">
          <span class="payment-id">${p.payment_id ?? "unknown"}</span>
          <span class="amount">₹${formatNumber(p.amount ?? 0)}</span>
          <span class="method">${p.payment_method ?? ""}</span>
          <span class="status-tag status-${status.toLowerCase()}">${toTitleCase(status)}</span>
          <span class="chevron">▸</span>
        </div>
        <div class="ledger-detail">
          <div class="flow">
            <div class="flow-step">
              <div class="flow-icon">✕</div>
              <div class="flow-content">
                <div class="flow-title">Failed</div>
                <div class="flow-body">${humanize(p.stage_1_original_failure?.reported_code ?? "")}</div>
              </div>
            </div>
            <div class="flow-connector"></div>
            <div class="flow-step">
              <div class="flow-icon">◎</div>
              <div class="flow-content">
                <div class="flow-title">Diagnosed as ${humanize(resolvedCode)}</div>
                <div class="flow-body">${methodLabel}${confidenceText}</div>
              </div>
            </div>
            <div class="flow-connector"></div>
            <div class="flow-step">
              <div class="flow-icon">${actionIcon}</div>
              <div class="flow-content">
                <div class="flow-title">${humanize(action)}</div>
                <div class="flow-body">${actionReasoning}</div>
              </div>
            </div>
            <div class="flow-connector"></div>
            <div class="flow-step">
              <div class="flow-icon">${outcomeIcon}</div>
              <div class="flow-content">
                <div class="flow-title">${humanize(status)}</div>
                <div class="flow-body">${retryCount} ${attemptWord}</div>
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

let currentRole = "admin";
let allPayments = [];
let currentMetrics = null;

async function init() {
  const [metrics, payments] = await Promise.all([
    fetch(`${API}/metrics`).then(r => r.json()),
    fetch(`${API}/payments`).then(r => r.json()),
  ]);

  currentMetrics = metrics;
  allPayments = payments;

  renderMetrics(metrics);
  renderFilterBar(metrics, payments);
  renderLedger(payments);
  setupRoleSwitcher();
}

function setupRoleSwitcher() {
  const switcher = document.getElementById("roleSwitcher");
  switcher.querySelectorAll(".role-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      switcher.querySelectorAll(".role-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentRole = btn.dataset.role;
      renderForRole(currentRole);
    });
  });
}

function renderForRole(role) {
  const metricsBand = document.getElementById("metricsBand");
  const filterBar = document.getElementById("filterBar");

  if (role === "admin") {
    metricsBand.style.display = "";
    filterBar.style.display = "";
    renderMetrics(currentMetrics);
    renderFilterBar(currentMetrics, allPayments);
    renderLedger(allPayments);
  } else if (role === "reviewer") {
    metricsBand.style.display = "none";
    filterBar.style.display = "none";
    renderReviewerQueue();
  } else if (role === "customer") {
    metricsBand.style.display = "none";
    filterBar.style.display = "none";
    renderCustomerInbox();
  }
}

function renderReviewerQueue() {
  const ledger = document.getElementById("ledger");
  const escalated = allPayments.filter(
    p => p.stage_4_execution.final_status === "ESCALATED"
  );

  if (escalated.length === 0) {
    ledger.innerHTML = `<div class="ledger-empty">No escalated payments pending review.</div>`;
    return;
  }

  ledger.innerHTML = `<h2 class="section-title">Escalated for review (${escalated.length})</h2>` +
    escalated.map(p => `
      <div class="review-card">
        <div class="review-header">
          <span class="payment-id">${p.payment_id}</span>
          <span class="amount">₹${formatNumber(p.amount)}</span>
        </div>
        <div class="review-reason-label">Failure diagnosis</div>
        <div class="review-reason">${humanize(p.stage_2_classification.resolved_code)} — ${p.stage_2_classification.reasoning}</div>
        <div class="review-reason-label">Why this was escalated</div>
        <div class="review-reason">${p.stage_3_recovery_decision.reasoning}</div>
      </div>
    `).join("");
}

function renderCustomerInbox() {
  const ledger = document.getElementById("ledger");
  const withNotifications = allPayments.filter(p => p.customer_notification);

  if (withNotifications.length === 0) {
    ledger.innerHTML = `<div class="ledger-empty">No notifications yet. Run the notification agent (batch_notify.py) to populate this view.</div>`;
    return;
  }

  ledger.innerHTML = `<h2 class="section-title">Notifications (${withNotifications.length})</h2>` +
    withNotifications.map(p => `
      <div class="inbox-card">
        <div class="inbox-meta">
          <span>${p.customer_name}</span>
          <span>₹${formatNumber(p.amount)}</span>
        </div>
        <p class="inbox-message">${p.customer_notification.message}</p>
      </div>
    `).join("");
}

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