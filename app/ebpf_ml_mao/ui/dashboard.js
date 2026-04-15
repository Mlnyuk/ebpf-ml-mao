const refreshMs = 15000;

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

function setStatus(state, timestamp) {
  const pill = byId('status-pill');
  pill.textContent = state;
  pill.className = `status-pill status-${state}`;
  byId('status-timestamp').textContent = `Updated ${new Date(timestamp * 1000).toLocaleString()}`;
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

function renderVerdictBars(verdicts) {
  const target = byId('verdict-bars');
  const entries = Object.entries(verdicts || {});
  if (!entries.length) {
    target.innerHTML = '<div class="empty">No workflow verdicts yet.</div>';
    return;
  }
  const max = Math.max(...entries.map(([, value]) => value), 1);
  target.innerHTML = entries.map(([label, value]) => {
    const width = Math.max((value / max) * 100, 8);
    return `
      <div class="bar-row">
        <span>${label}</span>
        <div class="bar-track"><span class="bar-fill" style="width:${width}%"></span></div>
        <strong>${value}</strong>
      </div>
    `;
  }).join('');
}

function applySnapshot(snapshot) {
  setStatus(snapshot.summary.state, snapshot.timestamp);
  byId('received-count').textContent = snapshot.ingest.received_count;
  byId('queue-count').textContent = snapshot.queue.count;
  byId('spool-count').textContent = snapshot.spool.count;
  byId('alert-count').textContent = snapshot.summary.alert_count;
  byId('active-model').textContent = snapshot.registry.active_model_id ?? 'missing';
  byId('model-count').textContent = snapshot.registry.model_count;
  byId('missing-artifacts').textContent = snapshot.registry.missing_artifact_count;
  byId('latest-verdict').textContent = snapshot.workflow.latest_verdict ?? '-';
  byId('workflow-nodes').textContent = (snapshot.workflow.nodes || []).length;
  byId('duplicate-count').textContent = snapshot.ingest.duplicates_count;
  byId('queue-pending').textContent = snapshot.queue.pending_count;
  byId('queue-failed').textContent = snapshot.queue.failed_count;
  byId('queue-age').textContent = formatAge(snapshot.queue.oldest_age_seconds);
  byId('spool-expired').textContent = snapshot.spool.expired_count;
  byId('spool-quarantined').textContent = snapshot.spool.quarantined_count;
  byId('spool-age').textContent = formatAge(snapshot.spool.oldest_age_seconds);
  renderAlerts(snapshot.alerts || []);
  renderVerdictBars(snapshot.workflow.verdicts || {});
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
    byId('alert-list').innerHTML = '<li class="empty">Unable to load dashboard snapshot.</li>';
  }
}

loadDashboard();
window.setInterval(loadDashboard, refreshMs);
