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

export function openPdf(path) {
  window.location.href = path;
}

export function primeCsrf() {
  return ensureCsrf().catch(() => {});
}
