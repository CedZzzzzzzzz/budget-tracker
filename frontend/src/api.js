export async function apiFetch(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  return fetch(path, {
    credentials: 'include',
    ...options,
    headers,
  });
}

export function openPdf(path) {
  window.location.href = path;
}
