/**
 * RecoverAI — Dashboard Application
 *
 * Vanilla JS SPA handling dashboard stats, payment table,
 * AI processing, human approval workflow, and audit log.
 */

// ── State ────────────────────────────────────────────────────────────────────
let currentTab = 'dashboard';
let paymentsData = [];
let pendingAuditId = null;  // for modal approval/rejection

// ── Helpers ──────────────────────────────────────────────────────────────────

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return res.json();
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function formatINR(n) {
  return '₹' + Number(n).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

function formatReason(r) {
  return r.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

const ACTION_ICONS = {
  retry_later: '🔄',
  send_payment_link: '🔗',
  request_alt_method: '💳',
  escalate_to_support: '🚨',
};

const ACTION_LABELS = {
  retry_later: 'Retry Later',
  send_payment_link: 'Send Payment Link',
  request_alt_method: 'Request Alt Method',
  escalate_to_support: 'Escalate to Support',
};

// ── Toast Notifications ──────────────────────────────────────────────────────

function showToast(message, type = 'info') {
  const container = $('#toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ── Tab Switching ────────────────────────────────────────────────────────────

function initTabs() {
  $$('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      if (target === currentTab) return;

      $$('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      $$('.tab-content').forEach(s => s.classList.remove('active'));
      $(`#${target}-section`).classList.add('active');

      currentTab = target;

      if (target === 'payments') loadPayments();
      if (target === 'audit') loadAuditLog();
    });
  });
}

// ── Counter Animation ────────────────────────────────────────────────────────

function animateValue(el, end, prefix = '', suffix = '', duration = 800) {
  const start = 0;
  const startTime = performance.now();

  function tick(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(start + (end - start) * eased);

    if (prefix === '₹') {
      el.textContent = prefix + current.toLocaleString('en-IN');
    } else {
      el.textContent = prefix + current + suffix;
    }

    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

// ── Dashboard ────────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const stats = await api('/api/dashboard');

    animateValue($('#val-total-failed'), Math.round(stats.total_failed_amount), '₹');
    animateValue($('#val-recoverable'), Math.round(stats.recoverable_amount), '₹');
    animateValue($('#val-recovery-rate'), Math.round(stats.recovery_rate), '', '%');
    animateValue($('#val-pending'), stats.pending_cases);

    $('#footer-total-cases').textContent = `${stats.total_cases} total cases`;
    $('#footer-recovered-cases').textContent = `${stats.recovered_cases} recovered`;
    $('#footer-escalated').textContent = `${stats.escalated_cases} escalated · ${stats.failed_cases} failed`;

    renderBarChart('bars-failure-reasons', stats.by_failure_reason);
    renderBarChart('bars-payment-methods', stats.by_payment_method);
  } catch (e) {
    showToast('Failed to load dashboard data', 'error');
    console.error(e);
  }
}

function renderBarChart(containerId, data) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  if (!data || Object.keys(data).length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No data available</div></div>';
    return;
  }

  // Sort by count descending
  const sorted = Object.entries(data).sort((a, b) => b[1].count - a[1].count);
  const maxCount = sorted[0][1].count;

  sorted.forEach(([key, val]) => {
    const pct = (val.count / maxCount) * 100;
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML = `
      <span class="bar-label" title="${formatReason(key)}">${formatReason(key)}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width: 0%"></div>
      </div>
      <span class="bar-value">${val.count}</span>
    `;
    container.appendChild(row);

    // Animate bar fill
    requestAnimationFrame(() => {
      setTimeout(() => {
        row.querySelector('.bar-fill').style.width = pct + '%';
      }, 50);
    });
  });
}

// ── Payments Table ───────────────────────────────────────────────────────────

async function loadPayments() {
  try {
    const status  = $('#filter-status').value;
    const method  = $('#filter-method').value;
    const segment = $('#filter-segment').value;

    let url = '/api/payments?';
    if (status) url += `status=${status}&`;
    if (method) url += `method=${method}&`;
    if (segment) url += `segment=${segment}&`;

    const data = await api(url);
    paymentsData = data.payments;
    $('#payments-count').textContent = `${data.total} payments`;

    renderPaymentsTable(data.payments);
  } catch (e) {
    showToast('Failed to load payments', 'error');
    console.error(e);
  }
}

function renderPaymentsTable(payments) {
  const tbody = $('#payments-tbody');
  tbody.innerHTML = '';

  if (payments.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="8">
        <div class="empty-state">
          <div class="empty-state-icon">📭</div>
          <div class="empty-state-text">No payments match the current filters</div>
        </div>
      </td></tr>`;
    return;
  }

  payments.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="payment-id">${p.payment_id}</span></td>
      <td><span class="amount">${formatINR(p.amount)}</span></td>
      <td><span class="method-badge">${p.payment_method}</span></td>
      <td>${formatReason(p.failure_reason)}</td>
      <td>${p.retry_count}</td>
      <td><span class="segment-badge segment-${p.customer_segment}">${p.customer_segment}</span></td>
      <td><span class="status-badge status-${p.recovery_status}">${p.recovery_status}</span></td>
      <td>
        <button class="btn btn-process btn-sm" onclick="processPayment('${p.payment_id}')"
                ${p.recovery_status === 'recovered' ? 'disabled' : ''}>
          ⚡ Analyze
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function initFilters() {
  ['filter-status', 'filter-method', 'filter-segment'].forEach(id => {
    document.getElementById(id).addEventListener('change', loadPayments);
  });
}

// ── AI Processing ────────────────────────────────────────────────────────────

async function processPayment(paymentId) {
  showToast('Running AI analysis...', 'info');

  try {
    const result = await api(`/api/payments/${paymentId}/process`, { method: 'POST' });

    if (result.error) {
      showToast(result.error, 'error');
      return;
    }

    if (result.stopped) {
      showToast(`⛔ ${result.stop_reason}`, 'warning');
      return;
    }

    showDecisionModal(paymentId, result);
    showToast('AI analysis complete', 'success');

    // Refresh data in background
    loadDashboard();
    if (currentTab === 'payments') loadPayments();
  } catch (e) {
    showToast('Failed to process payment', 'error');
    console.error(e);
  }
}

// ── Decision Modal ───────────────────────────────────────────────────────────

function showDecisionModal(paymentId, result) {
  pendingAuditId = result.audit_id;
  const c = result.classification;
  const r = result.recommendation;

  const body = $('#modal-body');
  body.innerHTML = `
    <div class="modal-section">
      <div class="modal-section-title">Payment Details</div>
      <div class="info-grid">
        <div class="info-item">
          <div class="info-label">Payment ID</div>
          <div class="info-value payment-id">${paymentId}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Audit ID</div>
          <div class="info-value" style="font-size:0.78rem; opacity:0.7">${result.audit_id}</div>
        </div>
      </div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">AI Classification</div>
      <div class="info-grid">
        <div class="info-item">
          <div class="info-label">Category</div>
          <div class="info-value">${formatReason(c.category)}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Confidence</div>
          <div class="info-value">${(c.confidence * 100).toFixed(0)}%</div>
          <div class="confidence-bar">
            <div class="confidence-fill" style="width: ${c.confidence * 100}%"></div>
          </div>
        </div>
      </div>
      <div class="reasoning-box" style="margin-top: 12px">
        ${c.reasoning}
      </div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">Recommended Action</div>
      <div style="margin-bottom: 12px">
        <span class="action-badge action-${r.action}">
          ${ACTION_ICONS[r.action] || '⚡'} ${ACTION_LABELS[r.action] || r.action}
        </span>
        <span class="status-badge status-${r.priority === 'critical' ? 'failed' : r.priority === 'high' ? 'escalated' : 'pending'}" style="margin-left: 8px">
          ${r.priority} priority
        </span>
      </div>
      <div class="reasoning-box">
        ${r.reasoning}
      </div>
    </div>

    <div class="modal-section">
      <div class="modal-section-title">Approval Status</div>
      <span class="status-badge status-${result.approval_status === 'awaiting_approval' ? 'pending' : 'recovered'}">
        ${result.approval_status.replace(/_/g, ' ')}
      </span>
      ${result.approval_status === 'awaiting_approval' ? '<span style="font-size: 0.82rem; color: var(--amber); margin-left: 10px">⚠️ Human approval required</span>' : ''}
    </div>

    ${result.approval_status === 'awaiting_approval' ? `
    <div class="modal-actions">
      <button class="btn btn-approve" id="btn-modal-approve" onclick="approveFromModal('${paymentId}', '${result.audit_id}')">
        ✓ Approve Action
      </button>
      <button class="btn btn-reject" id="btn-modal-reject" onclick="rejectFromModal('${paymentId}', '${result.audit_id}')">
        ✕ Reject
      </button>
    </div>
    ` : `
    <div class="modal-actions">
      <span style="font-size:0.85rem; color: var(--green)">✅ Action auto-approved and executed (simulated)</span>
    </div>
    `}
  `;

  $('#modal-overlay').classList.add('active');
}

function closeModal() {
  $('#modal-overlay').classList.remove('active');
  pendingAuditId = null;
}

async function approveFromModal(paymentId, auditId) {
  const btn = $('#btn-modal-approve');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Approving...';

  try {
    const result = await api(`/api/payments/${paymentId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ audit_id: auditId, approved_by: 'human_operator' }),
    });

    if (result.error) {
      showToast(result.error, 'error');
      btn.disabled = false;
      btn.innerHTML = '✓ Approve Action';
      return;
    }

    showToast('✅ Action approved and executed (simulated)', 'success');
    closeModal();
    loadDashboard();
    if (currentTab === 'payments') loadPayments();
  } catch (e) {
    showToast('Failed to approve action', 'error');
    btn.disabled = false;
    btn.innerHTML = '✓ Approve Action';
    console.error(e);
  }
}

async function rejectFromModal(paymentId, auditId) {
  const btn = $('#btn-modal-reject');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Rejecting...';

  try {
    const result = await api(`/api/payments/${paymentId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ audit_id: auditId, rejected_by: 'human_operator', reason: 'Manual review required' }),
    });

    if (result.error) {
      showToast(result.error, 'error');
      btn.disabled = false;
      btn.innerHTML = '✕ Reject';
      return;
    }

    showToast('❌ Action rejected', 'warning');
    closeModal();
    loadDashboard();
    if (currentTab === 'payments') loadPayments();
  } catch (e) {
    showToast('Failed to reject action', 'error');
    btn.disabled = false;
    btn.innerHTML = '✕ Reject';
    console.error(e);
  }
}

// ── Audit Log ────────────────────────────────────────────────────────────────

async function loadAuditLog() {
  try {
    const data = await api('/api/audit-log');
    $('#audit-count').textContent = `${data.total} entries`;
    renderAuditFeed(data.entries);
  } catch (e) {
    showToast('Failed to load audit log', 'error');
    console.error(e);
  }
}

function renderAuditFeed(entries) {
  const feed = $('#audit-feed');
  feed.innerHTML = '';

  if (entries.length === 0) {
    feed.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📋</div>
        <div class="empty-state-text">No audit entries yet. Process a payment to generate decisions.</div>
      </div>`;
    return;
  }

  entries.forEach(e => {
    const div = document.createElement('div');
    div.className = 'audit-entry';
    div.innerHTML = `
      <div class="audit-entry-header">
        <span class="audit-entry-id">${e.audit_id} · ${e.payment_id}</span>
        <span class="audit-entry-time">${formatDate(e.timestamp)}</span>
      </div>
      <div class="audit-entry-body">
        <div class="audit-field">
          <span class="audit-field-label">Action</span>
          <span class="audit-field-value">
            ${ACTION_ICONS[e.recommended_action] || '⚡'} ${ACTION_LABELS[e.recommended_action] || e.recommended_action}
          </span>
        </div>
        <div class="audit-field">
          <span class="audit-field-label">Approval</span>
          <span class="audit-field-value approval-${e.approval_status}">
            ${e.approval_status.replace(/_/g, ' ')}
          </span>
        </div>
        <div class="audit-field">
          <span class="audit-field-label">Result</span>
          <span class="audit-field-value">${e.execution_result || '—'}</span>
        </div>
        <div class="audit-reasoning">
          <strong>AI Reasoning:</strong> ${e.action_reasoning}
          ${e.notes ? `<br><strong>Notes:</strong> ${e.notes}` : ''}
        </div>
      </div>
    `;
    feed.appendChild(div);
  });
}

// ── Initialise ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initFilters();
  loadDashboard();

  // Modal close handlers
  $('#modal-close').addEventListener('click', closeModal);
  $('#modal-overlay').addEventListener('click', (e) => {
    if (e.target === $('#modal-overlay')) closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
});
