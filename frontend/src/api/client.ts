export interface VersionInfo {
  app: string
  core: string
}

export class ApiError extends Error {}

// FastAPI reports errors as {detail: string} or, for validation errors,
// {detail: [{msg: string, ...}]}.
function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => String((d as { msg?: unknown }).msg ?? ''))
      .map((m) => m.replace(/^Value error, /, ''))
      .join('. ')
  }
  return `Error del servidor (HTTP ${status})`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init)
  const body: unknown = resp.status === 204 ? null : await resp.json().catch(() => null)
  if (!resp.ok) throw new ApiError(errorMessage(body, resp.status))
  return body as T
}

export function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal })
}

export function postJson<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
}

export function putJson<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteJson(path: string): Promise<null> {
  return request<null>(path, { method: 'DELETE' })
}

export function fetchVersion(signal?: AbortSignal): Promise<VersionInfo> {
  return getJson<VersionInfo>('/api/version', signal)
}
