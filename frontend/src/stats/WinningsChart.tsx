import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

export interface GraphPoint {
  hand: number
  net: number
  showdown: number
  non_showdown: number
  allin_adj: number
}

type SeriesKey = 'net' | 'showdown' | 'non_showdown' | 'allin_adj'

const SERIES: { key: SeriesKey; label: string; color: string; dashed?: boolean }[] = [
  { key: 'net', label: 'Total', color: 'var(--series-total)' },
  { key: 'showdown', label: 'Con showdown', color: 'var(--series-showdown)' },
  { key: 'non_showdown', label: 'Sin showdown', color: 'var(--series-nonshowdown)' },
  { key: 'allin_adj', label: 'All-in EV', color: 'var(--series-ev)', dashed: true },
]

const HEIGHT = 280
const MARGIN = { top: 12, right: 16, bottom: 28, left: 56 }

function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) return [min]
  const raw = (max - min) / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const ticks: number[] = []
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(Number(v.toFixed(6)))
  return ticks
}

function fmt(v: number): string {
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}`
}

export function WinningsChart({ points }: { points: GraphPoint[] }) {
  const observer = useRef<ResizeObserver | null>(null)
  const [width, setWidth] = useState(640)
  const [hover, setHover] = useState<number | null>(null)

  // Callback ref: the plot only mounts once there is data, so measure it then.
  const wrap = useCallback((el: HTMLDivElement | null) => {
    observer.current?.disconnect()
    if (!el || typeof ResizeObserver === 'undefined') return
    observer.current = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    observer.current.observe(el)
  }, [])
  useEffect(() => () => observer.current?.disconnect(), [])

  const { x, y, yTicks, paths } = useMemo(() => {
    const maxHand = Math.max(1, points[points.length - 1]?.hand ?? 1)
    const values = points.flatMap((p) => SERIES.map((s) => p[s.key]))
    let lo = Math.min(0, ...values)
    let hi = Math.max(0, ...values)
    if (lo === hi) {
      lo -= 1
      hi += 1
    }
    const pad = (hi - lo) * 0.05
    lo -= pad
    hi += pad
    const innerW = width - MARGIN.left - MARGIN.right
    const innerH = HEIGHT - MARGIN.top - MARGIN.bottom
    const xs = (h: number) => MARGIN.left + (h / maxHand) * innerW
    const ys = (v: number) => MARGIN.top + (1 - (v - lo) / (hi - lo)) * innerH
    const d = (key: SeriesKey) =>
      points.map((p, i) => `${i === 0 ? 'M' : 'L'}${xs(p.hand).toFixed(1)},${ys(p[key]).toFixed(1)}`).join('')
    return {
      x: xs,
      y: ys,
      yTicks: niceTicks(lo, hi),
      paths: Object.fromEntries(SERIES.map((s) => [s.key, d(s.key)])) as Record<SeriesKey, string>,
    }
  }, [points, width])

  if (points.length < 2) return <p className="muted">Todavía no hay manos para graficar.</p>

  const lastPoint = points[points.length - 1]
  const active = hover === null ? null : points[hover]

  function pick(clientX: number, rect: DOMRect) {
    const hand = ((clientX - rect.left - MARGIN.left) / (width - MARGIN.left - MARGIN.right)) * lastPoint.hand
    let best = 0
    for (let i = 1; i < points.length; i++) {
      if (Math.abs(points[i].hand - hand) < Math.abs(points[best].hand - hand)) best = i
    }
    setHover(best)
  }

  return (
    <figure className="chart">
      <figcaption className="chart-title">Ganancias acumuladas (bb)</figcaption>
      <ul className="chart-legend">
        {SERIES.map((s) => (
          <li key={s.key}>
            <svg width="20" height="8" aria-hidden="true">
              <line
                x1="0"
                y1="4"
                x2="20"
                y2="4"
                stroke={s.color}
                strokeWidth="2"
                strokeDasharray={s.dashed ? '4 3' : undefined}
              />
            </svg>
            {s.label} <strong>{fmt(lastPoint[s.key])}</strong>
          </li>
        ))}
      </ul>
      <div className="chart-plot" ref={wrap}>
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`Ganancias acumuladas en ${lastPoint.hand} manos: total ${fmt(lastPoint.net)} bb`}
          tabIndex={0}
          onMouseMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
          onMouseLeave={() => setHover(null)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') setHover((h) => Math.min(points.length - 1, (h ?? -1) + 1))
            if (e.key === 'ArrowLeft') setHover((h) => Math.max(0, (h ?? points.length) - 1))
            if (e.key === 'Escape') setHover(null)
          }}
          onBlur={() => setHover(null)}
        >
          {yTicks.map((t) => (
            <g key={t}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={y(t)}
                y2={y(t)}
                className={t === 0 ? 'chart-zero' : 'chart-grid'}
              />
              <text x={MARGIN.left - 8} y={y(t)} className="chart-tick" textAnchor="end" dominantBaseline="middle">
                {t}
              </text>
            </g>
          ))}
          <text x={width - MARGIN.right} y={HEIGHT - 6} className="chart-tick" textAnchor="end">
            {lastPoint.hand} manos
          </text>
          {SERIES.map((s) => (
            <path
              key={s.key}
              d={paths[s.key]}
              fill="none"
              stroke={s.color}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
              strokeDasharray={s.dashed ? '6 4' : undefined}
            />
          ))}
          {active && (
            <g>
              <line x1={x(active.hand)} x2={x(active.hand)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} className="chart-crosshair" />
              {SERIES.map((s) => (
                <circle key={s.key} cx={x(active.hand)} cy={y(active[s.key])} r="4" fill={s.color} className="chart-dot" />
              ))}
            </g>
          )}
        </svg>
        {active && (
          <div
            className="chart-tooltip"
            style={{ left: Math.min(x(active.hand) + 12, width - 180), top: MARGIN.top }}
            role="status"
          >
            <div className="chart-tooltip-title">Mano {active.hand}</div>
            {SERIES.map((s) => (
              <div key={s.key} className="chart-tooltip-row">
                <svg width="14" height="8" aria-hidden="true">
                  <line x1="0" y1="4" x2="14" y2="4" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? '3 2' : undefined} />
                </svg>
                <span>{s.label}</span>
                <strong>{fmt(active[s.key])}</strong>
              </div>
            ))}
          </div>
        )}
      </div>
      <details className="chart-table">
        <summary>Ver como tabla</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Mano</th>
                {SERIES.map((s) => (
                  <th key={s.key} scope="col" className="num">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {points
                .filter((_, i) => i % Math.max(1, Math.ceil(points.length / 25)) === 0 || i === points.length - 1)
                .map((p) => (
                  <tr key={p.hand}>
                    <td>{p.hand}</td>
                    {SERIES.map((s) => (
                      <td key={s.key} className="num">
                        {fmt(p[s.key])}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}
