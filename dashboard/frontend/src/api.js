const API = '/api';

export async function fetchReports(signal) {
  const res = await fetch(`${API}/reports`, { signal });
  if (!res.ok) throw new Error(`fetchReports failed: ${res.status}`);
  return res.json();
}

export async function fetchReport(reportId, signal) {
  const res = await fetch(`${API}/reports/${reportId}`, { signal });
  if (!res.ok) throw new Error(`fetchReport failed: ${res.status}`);
  return res.json();
}

export async function generateReport({ startDate, endDate, noLlm, skipApify }) {
  const res = await fetch(`${API}/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_date: startDate, end_date: endDate, no_llm: noLlm, skip_apify: skipApify }),
  });
  if (!res.ok) throw new Error(`generateReport failed: ${res.status}`);
  return res.json();
}

export async function exportMarkdown(reportId, signal) {
  const res = await fetch(`${API}/reports/${reportId}/export/markdown`, { signal });
  if (!res.ok) throw new Error(`exportMarkdown failed: ${res.status}`);
  return res.text();
}

export async function exportHtml(reportId, signal) {
  const res = await fetch(`${API}/reports/${reportId}/export/html`, { signal });
  if (!res.ok) throw new Error(`exportHtml failed: ${res.status}`);
  return res.text();
}

export async function fetchFollowersSummary(reportId, signal) {
  const res = await fetch(`${API}/reports/${reportId}/followers`, { signal });
  if (!res.ok) throw new Error(`fetchFollowersSummary failed: ${res.status}`);
  return res.json();
}

export async function fetchGenerationLog(reportId, signal) {
  const res = await fetch(`${API}/reports/${reportId}/log`, { signal });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`fetchGenerationLog failed: ${res.status}`);
  return res.json();
}

export async function getSettings(signal) {
  const res = await fetch(`${API}/settings`, { signal });
  if (!res.ok) throw new Error(`getSettings failed: ${res.status}`);
  return res.json();
}

export async function saveSettings(body) {
  const res = await fetch(`${API}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`saveSettings failed: ${res.status}`);
  return res.json();
}

export async function getProfiles(signal) {
  const res = await fetch(`${API}/profiles`, { signal });
  if (!res.ok) throw new Error(`getProfiles failed: ${res.status}`);
  return res.json();
}

export async function saveProfiles(profiles) {
  const res = await fetch(`${API}/profiles`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profiles }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `saveProfiles failed: ${res.status}`);
  }
  return res.json();
}

export async function resetProfiles() {
  const res = await fetch(`${API}/profiles`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`resetProfiles failed: ${res.status}`);
  return res.json();
}

export function connectGenerateWS(onMessage) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/generate`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onerror = () => ws.close();
  return ws;
}
