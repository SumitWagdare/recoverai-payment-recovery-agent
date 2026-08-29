/**
 * RecoverAI — Dashboard Application
 * Premium Fintech 2026 Redesign
 */

// ── State ────────────────────────────────────────────────────────────────────
let currentTab = 'overview';
let paymentsData = [];
let pendingAuditId = null;

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

const ACTION_LABELS = {
  retry_later: 'Retry Later',
  send_payment_link: 'Send Payment Link',
  request_alt_method: 'Request Alt Method',
  escalate_to_support: 'Escalate',
};

// ── Tab Navigation ───────────────────────────────────────────────────────────

function initTabs() {
  $$('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      if (target === currentTab) return;

      $$('.nav-item').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      $$('.view-section').forEach(s => s.classList.remove('active'));
      $(`#view-${target}`).classList.add('active');

      currentTab = target;
      
      const titles = {
        overview: 'Overview',
        queue: 'Review Queue',
        payments: 'Payments Directory',
        audit: 'Audit Trail',
        evaluation: 'Batch Evaluation'
      };
      $('#topbar-title').textContent = titles[target] || 'Overview';

      // Load data based on tab
      if (target === 'queue') loadQueue();
      if (target === 'payments') loadPayments();
      if (target === 'audit') loadAuditLog();
      if (target === 'evaluation') loadEvaluation();
    });
  });
}

// ── Data Loaders ─────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const stats = await api('/api/dashboard');
    
    // Hero
    $('#hero-amount-risk').textContent = formatINR(stats.total_failed_amount);
    $('#hero-context').textContent = `${stats.total_cases} failed payments · ${stats.pending_cases} awaiting review`;
    
    // KPIs
    $('#kpi-rate').textContent = Math.round(stats.recovery_rate) + '%';
    $('#kpi-recovered').textContent = formatINR(stats.recoverable_amount);
    $('#kpi-recovered-cases').textContent = `${stats.recovered_cases} cases`;
    
    // Try to fetch evaluation for the delta
    try {
      const evalData = await api('/api/evaluation');
      const baselineRate = evalData.metrics?.baseline_recovery_rate || 28.3;
      const delta = (stats.recovery_rate - baselineRate).toFixed(1);
      $('#kpi-rate-delta').textContent = delta >= 0 ? `+${delta} pp vs baseline` : `${delta} pp vs baseline`;
    } catch (e) {
      // Ignore if evaluation endpoint fails
    }

    // We'll load recent payments to populate the Priority Queue and Activity Rail
    const paymentsRes = await api('/api/payments');
    const all = paymentsRes.payments || [];
    
    // Priority Queue (Pending, High value or customer facing)
    const pending = all.filter(p => p.recovery_status === 'pending');
    $('#nav-queue-count').textContent = pending.length;
    $('#kpi-review').textContent = pending.length;
    
    // Blocked (Failed/Escalated)
    const blocked = all.filter(p => p.recovery_status === 'failed' || p.recovery_status === 'escalated');
    $('#kpi-blocked').textContent = blocked.length;

    // Render Mini Priority Queue
    const priorityTable = $('#priority-tbody');
    priorityTable.innerHTML = '';
    pending.slice(0, 5).forEach(p => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span style="font-family:monospace;font-size:12px">${p.payment_id}</span></td>
        <td class="tabular-nums">${formatINR(p.amount)}</td>
        <td>${formatReason(p.failure_reason)}</td>
        <td><span class="badge badge-amber">Requires Review</span></td>
        <td><button class="btn btn-secondary btn-sm" onclick="openReview('${p.payment_id}')">Review</button></td>
      `;
      priorityTable.appendChild(tr);
    });
    
    if (pending.length === 0) {
      priorityTable.innerHTML = `<tr><td colspan="5" class="empty-state">Queue is empty</td></tr>`;
    }

    // Activity Rail
    loadActivityRail();
    
  } catch (e) {
    console.error('Failed to load dashboard', e);
  }
}

async function loadActivityRail() {
  try {
    const data = await api('/api/audit-log');
    const rail = $('#activity-rail');
    rail.innerHTML = '';
    
    if (!data.entries || data.entries.length === 0) {
      rail.innerHTML = '<div class="empty-state">No activity yet</div>';
      return;
    }
    
    data.entries.slice(0, 6).forEach(e => {
      let markerCls = 'marker-success';
      let statusText = 'Auto-approved retry';
      
      if (e.approval_status === 'awaiting_approval') {
        markerCls = 'marker-review';
        statusText = 'Routed to manual review';
      } else if (e.execution_result && e.execution_result.includes('blocked')) {
        markerCls = 'marker-blocked';
        statusText = 'Blocked by safety rule';
      }
      
      const div = document.createElement('div');
      div.className = 'activity-item';
      div.innerHTML = `
        <div class="activity-marker ${markerCls}"></div>
        <div class="activity-content">
          <div class="activity-header">
            <span class="activity-title">${statusText}</span>
            <span class="activity-time">${formatDate(e.timestamp).split(' ')[1]}</span>
          </div>
          <div class="activity-desc">
            ${e.payment_id} · ${ACTION_LABELS[e.recommended_action] || e.recommended_action}
          </div>
        </div>
      `;
      rail.appendChild(div);
    });
  } catch(e) {}
}

async function loadQueue() {
  const filter = $('#queue-filter').value;
  try {
    const data = await api('/api/payments?status=pending');
    let payments = data.payments || [];
    
    if (filter === 'high_value') {
      payments = payments.filter(p => p.amount >= 10000);
    } else if (filter === 'customer_facing') {
      // rough heuristic if we don't have the exact classification
      payments = payments.filter(p => p.failure_reason.includes('funds') || p.failure_reason.includes('pin'));
    }
    
    const tbody = $('#queue-tbody');
    tbody.innerHTML = '';
    
    if (payments.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No cases match filter</td></tr>`;
      return;
    }
    
    payments.forEach(p => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family:monospace;font-size:12px">${p.payment_id}</td>
        <td class="tabular-nums">${formatINR(p.amount)}</td>
        <td>${formatReason(p.failure_reason)}</td>
        <td><span class="badge badge-neutral">${p.customer_segment}</span></td>
        <td><span class="badge badge-amber">Manual Review</span></td>
        <td><button class="btn btn-secondary" onclick="openReview('${p.payment_id}')">Review Case</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error(e);
  }
}

async function loadPayments() {
  try {
    const status  = $('#pay-status').value;
    const method  = $('#pay-method').value;
    const segment = $('#pay-segment').value;

    let url = '/api/payments?';
    if (status) url += `status=${status}&`;
    if (method) url += `method=${method}&`;
    if (segment) url += `segment=${segment}&`;

    const data = await api(url);
    const tbody = $('#payments-tbody');
    tbody.innerHTML = '';

    if (data.payments.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No payments match filters</td></tr>`;
      return;
    }

    data.payments.forEach(p => {
      let bCls = 'badge-neutral';
      if (p.recovery_status === 'recovered') bCls = 'badge-emerald';
      if (p.recovery_status === 'failed' || p.recovery_status === 'escalated') bCls = 'badge-coral';
      if (p.recovery_status === 'pending') bCls = 'badge-amber';
      
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family:monospace;font-size:12px">${p.payment_id}</td>
        <td class="tabular-nums">${formatINR(p.amount)}</td>
        <td>${formatReason(p.failure_reason)}</td>
        <td>${p.retry_count}</td>
        <td><span class="badge badge-neutral">${p.customer_segment}</span></td>
        <td><span class="badge ${bCls}">${p.recovery_status}</span></td>
        <td>
          <button class="btn btn-secondary" onclick="openReview('${p.payment_id}')" ${p.recovery_status === 'recovered' ? 'disabled' : ''}>Analyze</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch(e) {}
}

async function loadAuditLog() {
  try {
    const data = await api('/api/audit-log');
    const tbody = $('#audit-tbody');
    tbody.innerHTML = '';
    
    if (!data.entries || data.entries.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No audit entries yet</td></tr>`;
      return;
    }
    
    data.entries.forEach(e => {
      let bCls = e.approval_status === 'awaiting_approval' ? 'badge-amber' : 'badge-emerald';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="tabular-nums text-secondary">${formatDate(e.timestamp)}</td>
        <td style="font-family:monospace;font-size:12px">${e.payment_id}</td>
        <td style="font-family:monospace;font-size:12px;opacity:0.6">${e.audit_id.substring(0,8)}...</td>
        <td>${ACTION_LABELS[e.recommended_action] || e.recommended_action}</td>
        <td><span class="badge ${bCls}">${e.approval_status.replace(/_/g, ' ')}</span></td>
        <td>${e.execution_result || '—'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch(e) {}
}

async function loadEvaluation() {
  try {
    const data = await api('/api/evaluation');
    const tbody = $('#eval-tbody');
    tbody.innerHTML = '';
    
    if (data.error) {
      tbody.innerHTML = `<tr><td colspan="4" class="empty-state text-coral">Run \`python scripts/run_batch.py\` to generate report</td></tr>`;
      return;
    }
    
    const baseline = data.baseline || {};
    const ai = data.ai_assisted || {};
    const stats = data.agent_stats || {};
    
    const baseRate = Number(baseline.recovery_rate || 0);
    const aiRate = Number(ai.recovery_rate || 0);
    const baseRev = Number(baseline.revenue_recovered || 0);
    const aiRev = Number(ai.revenue_recovered || 0);
    
    const rows = [
      { label: 'Recovery Rate', base: baseRate.toFixed(1) + '%', ai: aiRate.toFixed(1) + '%', delta: (aiRate - baseRate).toFixed(1) },
      { label: 'Simulated Revenue Recovered', base: formatINR(baseRev), ai: formatINR(aiRev), delta: formatINR(aiRev - baseRev) },
      { label: 'Recovered Cases', base: baseline.recovered || 0, ai: ai.recovered || 0, delta: (ai.recovered || 0) - (baseline.recovered || 0) },
      { label: 'Unsafe Actions Blocked', base: '—', ai: stats.unsafe_blocked || 0, delta: '—' },
      { label: 'Unresolved / Manual Review', base: '—', ai: data.unresolved_count || 0, delta: '—' },
      { label: 'Action Accuracy', base: '—', ai: (stats.action_accuracy_pct || 100).toFixed(1) + '%', delta: '—' }
    ];
    
    rows.forEach(r => {
      let isPos = false;
      let dPrefix = '';
      if (r.delta !== '—') {
        const dVal = typeof r.delta === 'string' ? parseFloat(r.delta.replace(/[^0-9.-]+/g,"")) : r.delta;
        isPos = dVal > 0;
        if (isPos && !String(r.delta).startsWith('+')) dPrefix = '+';
      }
      
      let dCls = 'text-secondary';
      if (r.delta !== '—' && r.label === 'Recovery Rate') dCls = isPos ? 'text-emerald' : 'text-secondary';
      else if (r.delta !== '—' && r.label === 'Simulated Revenue Recovered') dCls = isPos ? 'text-emerald' : 'text-secondary';
      else if (r.delta !== '—' && r.label === 'Recovered Cases') dCls = isPos ? 'text-emerald' : 'text-secondary';
      
      const deltaText = r.delta === '—' ? r.delta : (r.label === 'Recovery Rate' ? `${dPrefix}${r.delta} pp` : `${dPrefix}${r.delta}`);
      
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight:500">${r.label}</td>
        <td class="tabular-nums">${r.base}</td>
        <td class="tabular-nums">${r.ai}</td>
        <td class="tabular-nums ${dCls}">${deltaText}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch(e) {
    $('#eval-tbody').innerHTML = `<tr><td colspan="4" class="empty-state text-coral">Failed to load evaluation data</td></tr>`;
  }
}

// ── Review Drawer ────────────────────────────────────────────────────────────

async function openReview(paymentId) {
  $('#drawer-overlay').classList.add('active');
  $('#drawer-body').innerHTML = '<div class="spinner" style="margin:auto"></div>';
  $('#drawer-footer').innerHTML = '';
  
  try {
    // Process payment to get AI classification (simulates the agent)
    const result = await api(`/api/payments/${paymentId}/process`, { method: 'POST' });
    
    if (result.error) {
      $('#drawer-body').innerHTML = `<div class="text-coral">${result.error}</div>`;
      return;
    }
    
    if (result.stopped) {
      $('#drawer-body').innerHTML = `
        <div class="badge badge-coral mb-4">Safety Block</div>
        <div class="reasoning-box">${result.stop_reason}</div>
      `;
      $('#drawer-footer').innerHTML = `
        <button class="btn btn-secondary" style="flex:1" onclick="closeDrawer()">Dismiss</button>
      `;
      return;
    }
    
    pendingAuditId = result.audit_id;
    const c = result.classification;
    const r = result.recommendation;
    
    $('#drawer-body').innerHTML = `
      <div>
        <div class="detail-row">
          <span class="detail-label">Payment ID</span>
          <span class="detail-value" style="font-family:monospace">${paymentId}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Category</span>
          <span class="detail-value">${formatReason(c.category)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Confidence</span>
          <span class="detail-value text-cyan">${(c.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
      
      <div>
        <div class="detail-label mb-4" style="text-transform:uppercase;font-size:11px;letter-spacing:0.05em">AI Reasoning</div>
        <div class="reasoning-box">${c.reasoning}</div>
      </div>
      
      <div>
        <div class="detail-label mb-4" style="text-transform:uppercase;font-size:11px;letter-spacing:0.05em">Recommended Action</div>
        <div class="badge badge-cyan mb-4">${ACTION_LABELS[r.action] || r.action}</div>
        <div class="reasoning-box">${r.reasoning}</div>
      </div>
      
      <div>
        <div class="detail-label mb-4" style="text-transform:uppercase;font-size:11px;letter-spacing:0.05em">Approval Status</div>
        <div class="badge ${result.approval_status === 'awaiting_approval' ? 'badge-amber' : 'badge-emerald'}">${result.approval_status.replace(/_/g, ' ')}</div>
      </div>
    `;
    
    if (result.approval_status === 'awaiting_approval') {
      $('#drawer-footer').innerHTML = `
        <button class="btn btn-primary" style="flex:1" onclick="approveAction('${paymentId}', '${result.audit_id}')">Approve</button>
        <button class="btn btn-danger" onclick="rejectAction('${paymentId}', '${result.audit_id}')">Reject</button>
      `;
    } else {
      $('#drawer-footer').innerHTML = `
        <div style="font-size:13px; color:var(--status-emerald); text-align:center; width:100%">✅ Action auto-approved (simulated)</div>
      `;
    }
    
  } catch(e) {
    $('#drawer-body').innerHTML = `<div class="text-coral">Failed to load case details.</div>`;
  }
}

function closeDrawer() {
  $('#drawer-overlay').classList.remove('active');
  pendingAuditId = null;
}

async function approveAction(paymentId, auditId) {
  try {
    $('#drawer-footer').innerHTML = '<div class="spinner"></div>';
    await api(`/api/payments/${paymentId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ audit_id: auditId, approved_by: 'human_operator' })
    });
    closeDrawer();
    loadDashboard();
    if (currentTab === 'queue') loadQueue();
    if (currentTab === 'payments') loadPayments();
  } catch(e) {}
}

async function rejectAction(paymentId, auditId) {
  try {
    $('#drawer-footer').innerHTML = '<div class="spinner"></div>';
    await api(`/api/payments/${paymentId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ audit_id: auditId, rejected_by: 'human_operator', reason: 'Manual override' })
    });
    closeDrawer();
    loadDashboard();
    if (currentTab === 'queue') loadQueue();
    if (currentTab === 'payments') loadPayments();
  } catch(e) {}
}

// ── Initialise ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  loadDashboard();
  
  // Drawer close events
  $('#drawer-close').addEventListener('click', closeDrawer);
  $('#drawer-overlay').addEventListener('click', (e) => {
    if (e.target === $('#drawer-overlay')) closeDrawer();
  });
  
  // Filters
  ['queue-filter'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.addEventListener('change', loadQueue);
  });
  
  ['pay-status', 'pay-method', 'pay-segment'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.addEventListener('change', loadPayments);
  });
});
