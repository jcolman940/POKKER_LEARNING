import { useState } from 'react'
import { createPayout, deletePayout } from './api'
import type { Payout } from './types'

interface Props {
  payouts: Payout[]
  onChange: (payouts: Payout[]) => void
}

// Prizes are separated by ";" or whitespace; "6,5" and "6.5" are both 6.5 (a trailing
// comma, as in "50, 30, 20", is tolerated). Zero is allowed while the total is positive.
const PRIZE = /^\d+(?:[.,]\d+)?$/

function parsePrizes(text: string): number[] | null {
  const parts = text
    .split(/[;\s]+/)
    .map((p) => p.replace(/,$/, ''))
    .filter((p) => p !== '')
  if (parts.length === 0 || !parts.every((p) => PRIZE.test(p))) return null
  const nums = parts.map((p) => Number(p.replace(',', '.')))
  return nums.reduce((a, b) => a + b, 0) > 0 ? nums : null
}

export function PayoutsEditor({ payouts, onChange }: Props) {
  const [name, setName] = useState('')
  const [prizes, setPrizes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function add() {
    setError(null)
    if (!name.trim()) {
      setError('Poné un nombre a la estructura.')
      return
    }
    const nums = parsePrizes(prizes)
    if (!nums) {
      setError('Los premios deben ser números no negativos (con suma mayor que 0) separados por punto y coma o espacios, por ejemplo 30; 20; 14; 6,5.')
      return
    }
    setSaving(true)
    try {
      const created = await createPayout(name.trim(), nums)
      onChange([...payouts, created])
      setName('')
      setPrizes('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar la estructura')
    } finally {
      setSaving(false)
    }
  }

  async function remove(p: Payout) {
    setError(null)
    try {
      await deletePayout(p.id)
      onChange(payouts.filter((x) => x.id !== p.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo borrar la estructura')
    }
  }

  return (
    <fieldset className="trainer-group payouts-editor">
      <legend>Estructuras de premios</legend>
      <ul className="payout-list">
        {payouts.map((p) => (
          <li key={p.id}>
            <span className="payout-name">{p.name}</span>{' '}
            <span className="muted small">{p.payouts.join(' / ')}</span>
            {p.builtin ? (
              <span className="badge">Incluida</span>
            ) : (
              <button type="button" aria-label={`Borrar ${p.name}`} onClick={() => void remove(p)}>
                Borrar
              </button>
            )}
          </li>
        ))}
      </ul>
      <div className="trainer-row">
        <label>
          Nombre de la estructura
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Premios (separados por ; o espacios)
          <input
            type="text"
            value={prizes}
            placeholder="30; 20; 14; 6,5"
            onChange={(e) => setPrizes(e.target.value)}
          />
        </label>
        <button type="button" disabled={saving} onClick={() => void add()}>
          Agregar estructura
        </button>
      </div>
      {error && (
        <p className="error small" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  )
}
