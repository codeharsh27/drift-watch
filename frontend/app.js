/**
 * app.js — drift-watch redesigned logic
 */

'use strict';

const $ = id => document.getElementById(id);

// --- UTILITIES ---
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  } catch { return iso || '—'; }
}

// Flat shape generator for JS (to mimic Python backend for Step 2 visual)
function getShape(obj, prefix = '') {
  let shape = {};
  if (obj === null) return { [prefix || 'root']: 'NoneType' };
  
  if (Array.isArray(obj)) {
    shape[prefix || 'root'] = 'list';
    if (obj.length > 0) {
      Object.assign(shape, getShape(obj[0], prefix));
    }
  } else if (typeof obj === 'object') {
    shape[prefix || 'root'] = 'dict';
    for (const [k, v] of Object.entries(obj)) {
      const newKey = prefix ? `${prefix}.${k}` : k;
      Object.assign(shape, getShape(v, newKey));
    }
  } else {
    shape[prefix || 'root'] = typeof obj;
  }
  return shape;
}

// --- RENDERERS ---

function renderHeroWidget(vendors) {
  const container = $('hero-live-widget');
  if (!container) return;
  
  container.innerHTML = vendors.map(v => {
    const dotColor = v.has_drift ? 'red' : 'green';
    return `<div class="live-pill">
      <span class="dot ${dotColor}"></span>
      ${esc(v.name)}
      <span style="color:var(--text-muted);font-size:0.75rem;margin-left:8px;">${fmtTime(v.detected_at)}</span>
    </div>`;
  }).join('');
}

function renderPipelineSteps(vendor) {
  if (!vendor) return;
  
  const step1 = $('pipeline-step1');
  const step2 = $('pipeline-step2');
  const step3 = $('pipeline-step3');
  const step4Vendor = $('pipeline-step4-vendor');
  
  if (step1 && vendor.baseline) {
    step1.textContent = JSON.stringify(vendor.baseline, null, 2);
  } else if (step1) {
    step1.textContent = "{\n  // Awaiting first poll data\n}";
  }
  
  if (step2 && vendor.baseline) {
    step2.textContent = JSON.stringify(getShape(vendor.baseline), null, 2);
  }
  
  if (step3) {
    const diff = {
      removed: vendor.removed,
      added: vendor.added,
      type_changed: vendor.type_changed,
      has_drift: vendor.has_drift,
      drift_score: vendor.drift_score
    };
    step3.textContent = JSON.stringify(diff, null, 2);
  }
  
  if (step4Vendor) {
    step4Vendor.textContent = vendor.name;
  }
}

function renderDashboardTable(data) {
  const tbody = $('dash-tbody');
  const lastUpdated = $('dash-last-updated');
  if (!tbody) return;
  
  lastUpdated.textContent = `Last updated: ${fmtTime(data.generated_at)}`;
  
  tbody.innerHTML = data.vendors.map(v => {
    const statusText = v.has_drift ? 'Drift Detected' : 'Healthy';
    const dotClass = v.has_drift ? 'red' : 'green';
    const polls = v.stats ? v.stats.polls : 0;
    const drifts = v.stats ? v.stats.drifts_caught : 0;
    
    const badgeClass = v.has_drift ? 'drifted' : 'healthy';
    
    return `
      <tr>
        <td data-label="Vendor"><strong>${esc(v.name)}</strong></td>
        <td data-label="Endpoint"><span style="font-family:monospace;font-size:0.85rem;color:var(--text-muted);">${esc(v.description.replace('Live polling from ', ''))}</span></td>
        <td data-label="Status">
          <div class="status-badge ${badgeClass}">
            <span class="dot ${dotClass}" style="background-color: currentColor"></span>
            ${statusText}
          </div>
        </td>
        <td data-label="Last Polled">${fmtTime(v.detected_at)}</td>
        <td data-label="Polls">${polls}</td>
        <td data-label="Drifts">${drifts}</td>
        <td data-label="Score">
          <span class="score-badge" style="color: ${v.has_drift ? 'var(--status-red)' : 'var(--text-muted)'}">${v.drift_score}</span>
        </td>
      </tr>
    `;
  }).join('');
}

// --- MAIN FETCH ---
async function runScan() {
  const btn = $('btn-refresh');
  if (btn) {
    btn.textContent = "Refreshing...";
    btn.disabled = true;
  }
  
  const errEl = $('state-error');
  if (errEl) errEl.classList.add('hidden');
  
  try {
    const resp = await fetch('/api/report');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    
    if (data && data.vendors) {
      renderHeroWidget(data.vendors);
      renderDashboardTable(data);
      if (data.vendors.length > 0) {
        renderPipelineSteps(data.vendors[0]);
      }
    }
  } catch (err) {
    console.error('[drift-watch] Fetch failed:', err);
    if (errEl) errEl.classList.remove('hidden');
    
    const tbody = $('dash-tbody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:red;">Error fetching data</td></tr>`;
  } finally {
    if (btn) {
      btn.textContent = "Refresh Data";
      btn.disabled = false;
    }
  }
}

// --- PLAYGROUND ---
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
  resEl.classList.add('hidden');
  
  let beforeRaw = $('pg-before').value.trim();
  let afterRaw = $('pg-after').value.trim();

  if (!beforeRaw || !afterRaw) {
    errEl.textContent = 'Please enter JSON in both fields';
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
  btn.textContent = "Analyzing...";
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
    
    resEl.innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
    resEl.classList.remove('hidden');
    
  } catch (err) {
    console.error('[drift-watch] Playground failed:', err);
    errEl.textContent = 'API Error';
  } finally {
    btn.textContent = "Run Diff";
    btn.disabled = false;
  }
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
  // Mobile Nav Toggle
  const toggle = $('nav-toggle');
  const links = $('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', () => {
      links.classList.toggle('active');
    });
  }
  
  runScan();
});
