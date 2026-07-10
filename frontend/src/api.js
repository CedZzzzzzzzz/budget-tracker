let csrfToken = null;

async function ensureCsrf({ force = false } = {}) {
  if (!force && csrfToken) return csrfToken;
  const res = await fetch('/api/csrf-token', { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to fetch CSRF token');
  const data = await res.json();
  csrfToken = data.csrf_token;
  return csrfToken;
}

export function clearCsrf() {
  csrfToken = null;
}

export async function parseApiResponse(res) {
  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = {};
    }
  }
  return { data, ok: res.ok, status: res.status };
}

export async function apiFetch(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = { ...options.headers };
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  if (method !== 'GET' && method !== 'HEAD') {
    headers['X-CSRF-Token'] = await ensureCsrf();
  }

  let res = await fetch(path, {
    credentials: 'include',
    ...options,
    headers,
  });

  if (
    res.status === 403
    && method !== 'GET'
    && method !== 'HEAD'
  ) {
    const retryBody = await res.clone().json().catch(() => ({}));
    if (retryBody.error?.toLowerCase().includes('csrf')) {
      clearCsrf();
      headers['X-CSRF-Token'] = await ensureCsrf({ force: true });
      res = await fetch(path, {
        credentials: 'include',
        ...options,
        headers,
      });
    }
  }

  return res;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}

async function downloadResponse(res, fallbackName) {
  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = '/';
      return;
    }
    const text = await res.text();
    let message = `Export failed (${res.status})`;
    try {
      const data = JSON.parse(text);
      if (data.error) message = data.error;
    } catch {
      if (text && !text.includes('<html')) message = text;
    }
    throw new Error(message);
  }

  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition');
  const filename = disposition?.match(/filename="([^"]+)"/)?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function openPdf(path) {
  const res = await fetch(apiUrl(path), { credentials: 'include' });
  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = '/';
      return;
    }
    throw new Error(`PDF export failed (${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function downloadCsv(path) {
  const res = await fetch(apiUrl(path), { credentials: 'include' });
  await downloadResponse(res, 'budget-export.csv');
}

export async function runExport(task) {
  try {
    await task();
  } catch (err) {
    alert(err.message || 'Export failed. If running locally, restart the Flask server and try again.');
  }
}

export function primeCsrf() {
  return ensureCsrf().catch(() => {});
}
