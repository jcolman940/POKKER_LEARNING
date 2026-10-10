import { fireEvent, render, screen } from '@testing-library/react'
import { type ReactNode, useRef, useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Popover } from '.'

function Harness() {
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  return (
    <div>
      <button ref={anchor} type="button" onClick={() => setOpen(true)}>
        BTN
      </button>
      <button type="button">afuera</button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} label="Asiento BTN">
        <button type="button">Rival</button>
        <button type="button">Fold</button>
      </Popover>
    </div>
  )
}

function EditingHarness() {
  const [open, setOpen] = useState(true)
  const [stack, setStack] = useState('')
  const anchor = useRef<HTMLButtonElement>(null)
  return (
    <div>
      <button ref={anchor} type="button">
        BTN
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} label="Asiento BTN">
        <input aria-label="Apuesta" />
        <input aria-label="Stack" value={stack} onChange={(e) => setStack(e.target.value)} />
      </Popover>
    </div>
  )
}

function Bare({ children }: { children?: ReactNode }) {
  const [open, setOpen] = useState(true)
  const anchor = useRef<HTMLButtonElement>(null)
  return (
    <div>
      <button ref={anchor} type="button">
        ancla
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} label="Info">
        {children ?? <p>solo texto</p>}
      </Popover>
    </div>
  )
}

describe('Popover', () => {
  it('closes on Escape even with nothing focusable inside', () => {
    render(<Bare />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('focuses a link when it is the first control', () => {
    render(
      <Bare>
        <a href="#ayuda">Ayuda</a>
      </Bare>,
    )
    expect(screen.getByRole('link', { name: 'Ayuda' })).toHaveFocus()
  })

  it('keeps focus where the user is typing when the parent re-renders', () => {
    render(<EditingHarness />)
    const stack = screen.getByRole('textbox', { name: 'Stack' })
    stack.focus()
    fireEvent.change(stack, { target: { value: '93' } })
    expect(stack).toHaveFocus()
  })

  it('opens as a labelled dialog and focuses its first control', () => {
    render(<Harness />)
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'BTN' }))
    expect(screen.getByRole('dialog', { name: 'Asiento BTN' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rival' })).toHaveFocus()
  })

  it('closes on Escape and returns focus to the anchor', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'BTN' }))
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('button', { name: 'BTN' })).toHaveFocus()
  })

  it('closes on a click outside, but not inside or on the anchor', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'BTN' }))
    fireEvent.mouseDown(screen.getByRole('button', { name: 'Fold' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByRole('button', { name: 'BTN' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByRole('button', { name: 'afuera' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
