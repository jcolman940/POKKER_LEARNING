import { vi } from 'vitest'

type Handler = (body: unknown) => { status?: number; json: unknown }

/** Stubs global fetch with handlers keyed by "METHOD /path" (path prefix match). */
export function mockApi(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = (init?.method ?? 'GET').toUpperCase()
    const key = Object.keys(routes).find((k) => {
      const [m, path] = k.split(' ')
      return m === method && url.startsWith(path)
    })
    if (!key) return new Response(JSON.stringify({ detail: 'not mocked' }), { status: 404 })
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : init?.body
    const { status = 200, json } = routes[key](body)
    return new Response(JSON.stringify(json), { status })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
