import { afterEach, describe, expect, it, vi } from 'vitest'
import { startHeartbeat } from './heartbeat'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

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
})
