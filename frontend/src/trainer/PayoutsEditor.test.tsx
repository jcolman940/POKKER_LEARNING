import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { PayoutsEditor } from './PayoutsEditor'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function submit(prizes: string) {
  const posted: unknown[] = []
  mockApi({
    'POST /api/trainer/payouts': (body) => {
      posted.push(body)
      return { status: 201, json: { id: 9, name: 'Mi estructura', payouts: [], builtin: false } }
    },
  })
  const onChange = vi.fn()
  render(<PayoutsEditor payouts={[]} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('Nombre de la estructura'), { target: { value: 'Mi estructura' } })
  fireEvent.change(screen.getByLabelText(/^Premios/), { target: { value: prizes } })
  fireEvent.click(screen.getByRole('button', { name: 'Agregar estructura' }))
  return { posted, onChange }
}

describe('PayoutsEditor parsing', () => {
  it.each([
    ['30; 20; 14; 6,5', [30, 20, 14, 6.5]],
    ['30; 20; 14; 6.5', [30, 20, 14, 6.5]],
    ['50 30 20', [50, 30, 20]],
    ['50; 30; 0', [50, 30, 0]],
    ['50, 30, 20', [50, 30, 20]],
  ])('accepts %s', async (text, expected) => {
    const { posted, onChange } = await submit(text)
    await waitFor(() => expect(onChange).toHaveBeenCalled())
    expect(posted).toEqual([{ name: 'Mi estructura', payouts: expected }])
  })

  it.each(['-5; 10', 'abc; 10', '0; 0', '50,30,20x', ';;'])('rejects %s', async (text) => {
    const { posted } = await submit(text)
    expect(await screen.findByRole('alert')).toHaveTextContent(/premios/i)
    expect(posted).toEqual([])
  })

  it('explains the format', () => {
    mockApi({})
    render(<PayoutsEditor payouts={[]} onChange={vi.fn()} />)
    expect(screen.getByPlaceholderText('30; 20; 14; 6,5')).toBeInTheDocument()
  })
})
