export async function apiRequest(
  kind,
  path,
  { method = 'GET', body, token = '' } = {},
) {
  if (!['apex', 'lwc', 'default'].includes(kind)) {
    throw new Error('Unsupported implementation type.');
  }

  const url = kind === 'default'
    ? `/api${path}`
    : `/api/${kind}${path}`;

  const response = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(body !== undefined
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...(token
        ? { Authorization: `Bearer ${token}` }
        : {}),
    },
    ...(body !== undefined
      ? { body: JSON.stringify(body) }
      : {}),
    cache: 'no-store',
  });

  const text = await response.text();
  let result;

  try {
    result = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(
      `Backend returned a non-JSON response (${response.status}). `
      + 'Check the API proxy.',
    );
  }

  if (!response.ok) {
    const detail = typeof result.detail === 'string'
      ? result.detail
      : result.detail?.message || JSON.stringify(result.detail || result);

    const error = new Error(
      detail || `Request failed (${response.status}).`,
    );

    error.status = response.status;
    error.detail = result.detail;

    if (
      response.status === 401
      && !path.startsWith('/auth/')
    ) {
      window.location.assign('/login');
    }

    throw error;
  }

  return result;
}