import { afterEach, describe, expect, it, vi } from 'vitest'
import { startHeartbeat } from './heartbeat'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  setVisibility('visible')
})

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
}

function becomeVisible() {
  setVisibility('visible')
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('startHeartbeat', () => {
  it('posts to /api/app/ping on an interval and stops on cleanup', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetchMock)
    const stop = startHeartbeat(10000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/app/ping')
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' })
    await vi.advanceTimersByTimeAsync(20000)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    stop()
    await vi.advanceTimersByTimeAsync(30000)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('ignores network errors', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    const stop = startHeartbeat(1000)
    await vi.advanceTimersByTimeAsync(3000)
    stop()
  })

  it('pings right away when the tab becomes visible again', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    const stop = startHeartbeat(10000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    setVisibility('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    becomeVisible()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/app/ping')
    stop()
    becomeVisible()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('reports the server down after two failed pings in a row, and up again', async () => {
    vi.useFakeTimers()
    let ok = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        if (ok) return new Response(null, { status: 204 })
        throw new TypeError('Failed to fetch')
      }),
    )
    const onDown = vi.fn()
    const stop = startHeartbeat(1000, onDown)
    await vi.advanceTimersByTimeAsync(0)
    expect(onDown).not.toHaveBeenCalled() // one failure is not enough
    await vi.advanceTimersByTimeAsync(1000)
    expect(onDown).toHaveBeenCalledTimes(1)
    expect(onDown).toHaveBeenLastCalledWith(true)
    await vi.advanceTimersByTimeAsync(1000)
    expect(onDown).toHaveBeenCalledTimes(1) // only on changes
    ok = true
    await vi.advanceTimersByTimeAsync(1000)
    expect(onDown).toHaveBeenLastCalledWith(false)
    stop()
  })

  it('counts HTTP errors as failed pings', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 502 })))
    const onDown = vi.fn()
    const stop = startHeartbeat(1000, onDown)
    await vi.advanceTimersByTimeAsync(1000)
    expect(onDown).toHaveBeenCalledWith(true)
    stop()
  })
})
