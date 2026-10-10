import { getJson, postJson } from '../api/client'

export async function importCharts(file: File): Promise<{ created: number; errors: string[] }> {
  const body: unknown = JSON.parse(await file.text())
  return postJson<{ created: number; errors: string[] }>('/api/charts/import', body)
}

export function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export async function exportCharts(onlyOwn: boolean): Promise<void> {
  const query = onlyOwn ? '?source=custom&source=computed' : ''
  const data = await getJson<unknown>(`/api/charts/export${query}`)
  download(onlyOwn ? 'rangos-propios.json' : 'rangos.json', data)
}
