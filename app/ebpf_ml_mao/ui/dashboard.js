const refreshMs = 15000;
const scoreThreshold = 0.45;

function byId(id) {
  return document.getElementById(id);
}

function formatAge(value) {
  if (value === null || value === undefined) return '-';
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return `${minutes}m ${seconds}s`;
}

function fmtScore(value) {
  return value === null || value === undefined ? '—' : Number(value).toFixed(3);
}

function fmtPct(value) {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(0)}%`;
}

function setStatus(state, timestamp) {
  const pill = byId('status-pill');
  pill.textContent = state;
  pill.className = `status-pill status-${state}`;
  byId('status-timestamp').textContent = `Updated ${new Date(timestamp * 1000).toLocaleString()}`;
}

function verdictClass(verdict) {
  if (verdict === 'anomalous') return 'critical';
  if (verdict === 'normal') return 'ok';
  return 'warning';
}

function sparkline(history) {
  const points = (history || []).filter((p) => p.score !== null && p.score !== undefined);
  if (points.length < 2) {
    return '<div class="spark-empty">not enough samples for trend</div>';
  }
  const w = 240;
  const h = 56;
  const pad = 4;
  const n = points.length;
  const x = (i) => pad + (i * (w - 2 * pad)) / (n - 1);
  const y = (s) => h - pad - Math.max(0, Math.min(1, s)) * (h - 2 * pad);
  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.score).toFixed(1)}`).join(' ');
  const thresholdY = y(scoreThreshold).toFixed(1);
  const dots = points
    .map((p, i) => {
      const cls = p.verdict === 'anomalous' ? 'dot-anom' : 'dot-norm';
      return `<circle class="${cls}" cx="${x(i).toFixed(1)}" cy="${y(p.score).toFixed(1)}" r="2.4" />`;
    })
    .join('');
  return `
    <svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="score trend">
      <line class="spark-threshold" x1="${pad}" y1="${thresholdY}" x2="${w - pad}" y2="${thresholdY}" />
      <polyline class="spark-line" points="${line}" />
      ${dots}
    </svg>`;
}

function workloadCard(name, data) {
  const verdict = data.latest_verdict || 'unknown';
  const cls = verdictClass(verdict);
  const top = data.top_feature;
  const topChip = top
    ? `<span class="feature-chip">${top.name} = ${Number(top.value).toFixed(2)}</span>`
    : '<span class="feature-chip muted">no feature signal</span>';
  return `
    <article class="workload-card accent-${cls}">
      <div class="wl-head">
        <h3 class="wl-name">${name}</h3>
        <span class="status-pill status-${cls}">${verdict}</span>
      </div>
      <div class="wl-score">
        <span class="wl-score-value">${fmtScore(data.latest_score)}</span>
        <span class="wl-score-label">anomaly score</span>
      </div>
      <div class="wl-spark">${sparkline(data.recent_scores)}</div>
      <div class="wl-meta">
        <div><dt>Top feature</dt><dd>${topChip}</dd></div>
        <div><dt>Detection</dt><dd>${fmtPct(data.detection_rate)} (${data.anomalous_count}/${data.sample_count})</dd></div>
        <div><dt>Node</dt><dd>${data.latest_node || '-'}</dd></div>
      </div>
    </article>`;
}

function renderWorkloads(workloads) {
  const grid = byId('workload-grid');
  const names = Object.keys(workloads || {});
  if (!names.length) {
    grid.innerHTML = '<div class="empty">No workload scores yet. Waiting for analyzer reports.</div>';
    return;
  }
  // Anomalous first, then by sample count desc.
  names.sort((a, b) => {
    const aw = workloads[a].latest_verdict === 'anomalous' ? 0 : 1;
    const bw = workloads[b].latest_verdict === 'anomalous' ? 0 : 1;
    if (aw !== bw) return aw - bw;
    return (workloads[b].sample_count || 0) - (workloads[a].sample_count || 0);
  });
  grid.innerHTML = names.map((name) => workloadCard(name, workloads[name])).join('');
}

function renderAlerts(alerts) {
  const list = byId('alert-list');
  if (!alerts.length) {
    list.innerHTML = '<li class="empty">No active alerts.</li>';
    return;
  }
  list.innerHTML = alerts.map((alert) => `
    <li class="alert-item ${alert.severity}">
      <div class="alert-top">
        <span class="alert-name">${alert.name}</span>
        <span class="status-pill status-${alert.severity}">${alert.severity}</span>
      </div>
      <p class="alert-message">${alert.message}</p>
      <p class="meta">value: ${alert.value} | threshold: ${alert.threshold ?? '-'}</p>
    </li>
  `).join('');
}

function applySnapshot(snapshot) {
  setStatus(snapshot.summary.state, snapshot.timestamp);
  byId('received-count').textContent = snapshot.ingest.received_count;
  byId('queue-count').textContent = snapshot.queue.count;
  byId('spool-count').textContent = snapshot.spool.count;
  byId('alert-count').textContent = snapshot.summary.alert_count;
  const activeModel = snapshot.registry.active_model_id ?? 'missing';
  byId('active-model').textContent = activeModel;
  byId('active-model-2').textContent = activeModel;
  byId('model-count').textContent = snapshot.registry.model_count;
  byId('missing-artifacts').textContent = snapshot.registry.missing_artifact_count;
  byId('queue-pending').textContent = snapshot.queue.pending_count;
  byId('queue-failed').textContent = snapshot.queue.failed_count;
  byId('queue-age').textContent = formatAge(snapshot.queue.oldest_age_seconds);
  byId('spool-expired').textContent = snapshot.spool.expired_count;
  byId('spool-quarantined').textContent = snapshot.spool.quarantined_count;
  byId('spool-age').textContent = formatAge(snapshot.spool.oldest_age_seconds);
  renderAlerts(snapshot.alerts || []);
  renderWorkloads((snapshot.workflow || {}).workloads || {});
}

async function loadDashboard() {
  try {
    const response = await fetch('/v1/dashboard', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const snapshot = await response.json();
    applySnapshot(snapshot);
  } catch (error) {
    byId('status-pill').textContent = 'critical';
    byId('status-pill').className = 'status-pill status-critical';
    byId('status-timestamp').textContent = `Dashboard fetch failed: ${error.message}`;
    byId('workload-grid').innerHTML = '<div class="empty">Unable to load dashboard snapshot.</div>';
  }
}

loadDashboard();
window.setInterval(loadDashboard, refreshMs);
