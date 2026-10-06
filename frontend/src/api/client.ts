export interface VersionInfo {
  app: string
  core: string
}

export async function fetchVersion(signal?: AbortSignal): Promise<VersionInfo> {
  const resp = await fetch('/api/version', { signal })
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`)
  }
  return (await resp.json()) as VersionInfo
}
