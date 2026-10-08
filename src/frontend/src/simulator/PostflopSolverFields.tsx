import { RangeEditor } from './RangeEditor'

interface Props {
  heroRange: string
  onHeroRange: (v: string) => void
  preset: string
  onPreset: (v: string) => void
  presets: { name: string; label: string }[]
  prefill: () => Promise<void>
  prefillNotes: string[]
  potType: 'srp' | '3bet'
  onPotType: (v: 'srp' | '3bet') => void
  aggressor: 'hero' | 'villain'
  onAggressor: (v: 'hero' | 'villain') => void
}

export function PostflopSolverFields(p: Props) {
  return (
    <fieldset className="solver-fields">
      <legend>Solver postflop (heads-up)</legend>
      <div className="row">
        <label>
          Pote
          <select value={p.potType} onChange={(e) => p.onPotType(e.target.value as 'srp' | '3bet')}>
            <option value="srp">Simple (open + call)</option>
            <option value="3bet">3-bet</option>
          </select>
        </label>
        <label>
          Agresor preflop
          <select
            value={p.aggressor}
            onChange={(e) => p.onAggressor(e.target.value as 'hero' | 'villain')}
          >
            <option value="hero">Hero</option>
            <option value="villain">Rival 1</option>
          </select>
        </label>
        <button type="button" onClick={() => void p.prefill()}>
          Prellenar desde tablas
        </button>
        <label>
          Árbol
          <select value={p.preset} onChange={(e) => p.onPreset(e.target.value)}>
            {p.presets.map((x) => (
              <option key={x.name} value={x.name}>
                {x.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {p.prefillNotes.length > 0 && (
        <div className="small">
          <span className="badge badge-warn">Aproximado</span>
          <ul>
            {p.prefillNotes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      )}
      <label htmlFor="hero-range">Rango de Hero</label>
      <RangeEditor id="hero-range" value={p.heroRange} onChange={p.onHeroRange} />
    </fieldset>
  )
}
