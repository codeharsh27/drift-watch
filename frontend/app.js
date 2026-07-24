/**
 * app.js — drift-watch dashboard logic
 *
 * Responsibilities:
 *  - Fetch /api/report from the FastAPI server
 *  - Render summary strip, vendor cards, and raw JSON
 *  - Handle tab switching within each vendor card
 *  - Animate drift score bars on load
 *  - Provide runScan() and goScan() for button handlers
 */

'use strict';

// ─── UTILITIES ────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const show = id => $(id).classList.remove('hidden');
const hide = id => $(id).classList.add('hidden');

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function scoreClass(n) {
  if (n >= 50) return 'high';
  if (n >= 20) return 'med';
  return 'low';
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  } catch { return iso || '—'; }
}

// ─── SUMMARY STRIP ────────────────────────────────────────────
function renderSummary(data) {
  const { summary } = data;

  $('s-total').textContent   = summary.total_vendors;
  $('s-drifted').textContent = summary.vendors_with_drift;
  $('s-time').textContent    = fmtTime(data.generated_at);

  const el = $('s-status');
  if (summary.overall_status === 'CRITICAL') {
    el.textContent  = 'CRITICAL';
    el.className    = 'sum-val vc';
  } else {
    el.textContent  = 'STABLE';
    el.className    = 'sum-val vs';
  }
}

// ─── TABLE RENDERERS ──────────────────────────────────────────
function removedTable(rows) {
  if (!rows.length) return emptyTab('✓', 'No fields were removed');
  const trs = rows.map(r => `
    <tr>
      <td><span class="fpath">${esc(r.field)}</span></td>
      <td><span class="tpill tp-crit">${esc(r.was_type)}</span></td>
      <td><span class="vpreview" title="${esc(r.before_value)}">${esc(r.before_value)}</span></td>
    </tr>`).join('');
  return `<table class="dtable">
    <thead><tr><th>Field Path</th><th>Was Type</th><th>Before Value</th></tr></thead>
    <tbody>${trs}</tbody>
  </table>`;
}

function changedTable(rows) {
  if (!rows.length) return emptyTab('✓', 'No type changes detected');
  const trs = rows.map(r => `
    <tr>
      <td><span class="fpath">${esc(r.field)}</span></td>
      <td>
        <span class="tpill tp-crit">${esc(r.was)}</span>
        &nbsp;→&nbsp;
        <span class="tpill tp-warn">${esc(r.now)}</span>
      </td>
      <td>
        <span class="vpreview" title="${esc(r.before_value)} → ${esc(r.after_value)}">
          ${esc(r.before_value)} → ${esc(r.after_value)}
        </span>
      </td>
    </tr>`).join('');
  return `<table class="dtable">
    <thead><tr><th>Field Path</th><th>Type Change</th><th>Value Change</th></tr></thead>
    <tbody>${trs}</tbody>
  </table>`;
}

function addedTable(rows) {
  if (!rows.length) return emptyTab('—', 'No new fields appeared');
  const trs = rows.map(r => `
    <tr>
      <td><span class="fpath">${esc(r.field)}</span></td>
      <td><span class="tpill tp-info">${esc(r.new_type)}</span></td>
      <td><span class="vpreview" title="${esc(r.after_value)}">${esc(r.after_value)}</span></td>
    </tr>`).join('');
  return `<table class="dtable">
    <thead><tr><th>Field Path</th><th>New Type</th><th>Value</th></tr></thead>
    <tbody>${trs}</tbody>
  </table>`;
}

function emptyTab(icon, msg) {
  return `<div class="empty-tab"><div class="et-icon">${icon}</div>${msg}</div>`;
}

// ─── VENDOR CARD ──────────────────────────────────────────────
function vendorCard(v, idx) {
  const sc = scoreClass(v.drift_score || 0);
  const hasDrift = v.has_drift;
  const cid = `vc${idx}`;

  return `
  <div class="vcard ${hasDrift ? 'vc-drift' : 'vc-clean'}" id="${cid}">

    <div class="vc-head">
      <div>
        <div class="vc-name">${esc(v.name)}</div>
        <div class="vc-desc">${esc(v.description || '')}</div>
      </div>
      <span class="bdg ${hasDrift ? 'bdg-drift' : 'bdg-clean'}">
        ${hasDrift ? '⚠ DRIFT' : '✓ CLEAN'}
      </span>
    </div>

    <div class="vc-score">
      <div class="vc-score-row">
        <span class="vc-score-lbl">Drift Score</span>
        <span class="vc-score-num sn-${sc}">${v.drift_score || 0} / 100</span>
      </div>
      <div class="score-bar">
        <div class="score-fill sf-${sc}" id="sf-${cid}"></div>
      </div>
    </div>

    <div class="vc-tabs" data-cid="${cid}">
      <button class="tbn t-crit active" data-panel="p-rm-${cid}">
        Removed (${v.removed.length})
      </button>
      <button class="tbn t-crit" data-panel="p-tc-${cid}">
        Type Changed (${v.type_changed.length})
      </button>
      <button class="tbn" data-panel="p-add-${cid}">
        Added (${v.added.length})
      </button>
    </div>

    <div class="tpanel active" id="p-rm-${cid}">
      ${removedTable(v.removed)}
    </div>
    <div class="tpanel" id="p-tc-${cid}">
      ${changedTable(v.type_changed)}
    </div>
    <div class="tpanel" id="p-add-${cid}">
      ${addedTable(v.added)}
    </div>
  </div>`;
}

// ─── RENDER VENDOR CARDS ──────────────────────────────────────
function renderCards(data) {
  const grid = $('cards-grid');
  grid.innerHTML = data.vendors.map(vendorCard).join('');

  // Animate score bars after brief delay (allows DOM paint)
  setTimeout(() => {
    data.vendors.forEach((v, i) => {
      const bar = $(`sf-vc${i}`);
      if (bar) bar.style.width = `${Math.min(100, v.drift_score || 0)}%`;
    });
  }, 120);

  initTabs();
}

// ─── TAB SWITCHING ────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.vc-tabs').forEach(group => {
    group.querySelectorAll('.tbn').forEach(btn => {
      btn.addEventListener('click', () => {
        const panelId = btn.dataset.panel;
        const card    = btn.closest('.vcard');

        group.querySelectorAll('.tbn').forEach(b => b.classList.remove('active'));
        card.querySelectorAll('.tpanel').forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        const panel = document.getElementById(panelId);
        if (panel) panel.classList.add('active');
      });
    });
  });
}

// ─── RAW JSON ─────────────────────────────────────────────────
function renderRaw(data) {
  $('raw-pre').textContent = JSON.stringify(data, null, 2);
  show('raw-wrap');
}

// ─── MAIN SCAN FLOW ───────────────────────────────────────────
async function runScan() {
  const btn  = $('btn-rescan');
  const icon = $('rescan-icon');

  // Loading state
  btn.classList.add('loading');
  btn.disabled = true;
  show('state-loading');
  hide('state-error');
  hide('cards-grid');
  hide('raw-wrap');

  try {
    const resp = await fetch('/api/report');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    hide('state-loading');
    show('cards-grid');

    renderSummary(data);
    renderCards(data);
    renderRaw(data);

  } catch (err) {
    console.error('[drift-watch] Scan failed:', err);
    hide('state-loading');
    show('state-error');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

// ─── PLAYGROUND ───────────────────────────────────────────────
function fillPlaygroundExample() {
  $('pg-before').value = JSON.stringify({
    "id": "req_123",
    "model": "gpt-4",
    "usage": {
      "prompt_tokens": 100,
      "completion_tokens": 50,
      "cost": 0.005
    }
  }, null, 2);

  $('pg-after').value = JSON.stringify({
    "id": "req_123",
    "model": "gpt-4",
    "usage": {
      "prompt_tokens": 100,
      "completion_tokens": 50
    },
    "billing": {
      "cost_str": "0.005"
    }
  }, null, 2);
  
  $('pg-error').textContent = '';
}

async function runPlaygroundDiff() {
  const errEl = $('pg-error');
  const resEl = $('pg-results');
  errEl.textContent = '';
  hide('pg-results');
  
  let beforeRaw = $('pg-before').value.trim();
  let afterRaw = $('pg-after').value.trim();

  if (!beforeRaw || !afterRaw) {
    errEl.textContent = 'Please enter JSON in both fields or click "Load Example"';
    return;
  }

  let beforeJson, afterJson;
  try {
    beforeJson = JSON.parse(beforeRaw);
  } catch (e) {
    errEl.textContent = 'Invalid Baseline JSON';
    return;
  }
  try {
    afterJson = JSON.parse(afterRaw);
  } catch (e) {
    errEl.textContent = 'Invalid Current JSON';
    return;
  }

  const btn = $('btn-run-diff');
  const originalText = btn.innerHTML;
  btn.innerHTML = `<span class="spinner" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:8px;"></span> Analyzing...`;
  btn.disabled = true;

  try {
    const resp = await fetch('/api/diff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        before_json: beforeJson,
        after_json: afterJson
      })
    });
    
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const result = await resp.json();
    
    // Format as a pseudo-vendor for the vendorCard renderer
    const pseudoVendor = {
      name: "Playground Result",
      description: "Live diff evaluation",
      ...result
    };
    
    resEl.innerHTML = vendorCard(pseudoVendor, 'pg');
    show('pg-results');
    
    // Animate score bar
    setTimeout(() => {
      const bar = $(`sf-vcpg`);
      if (bar) bar.style.width = `${Math.min(100, result.drift_score || 0)}%`;
    }, 50);
    
    initTabs();
    
  } catch (err) {
    console.error('[drift-watch] Playground diff failed:', err);
    errEl.textContent = 'API Error: Could not run diff';
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

// ─── NAV HELPERS ──────────────────────────────────────────────
function goScan() {
  const el = $('scan');
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  runScan();
});
