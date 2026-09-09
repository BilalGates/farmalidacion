import { useEffect, useId, useRef, useState } from 'react'

import type { Reviewer } from '../api/types'

export function ReviewerSelect({
  reviewers,
  value,
  onChange,
}: {
  reviewers: Reviewer[]
  value: string
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const listId = useId()
  const selected = reviewers.find((item) => item.identifier === value) ?? null

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  function choose(identifier: string) {
    onChange(identifier)
    setOpen(false)
  }

  return (
    <div className='reviewer-select' ref={root}>
      <button
        type='button'
        className='reviewer-select__trigger'
        role='combobox'
        aria-label='Revisor que firma las decisiones'
        aria-controls={listId}
        aria-expanded={open}
        aria-haspopup='listbox'
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false)
          if (event.key === 'ArrowDown') {
            event.preventDefault()
            setOpen(true)
          }
        }}
      >
        <span className='reviewer-picker__avatar' aria-hidden='true'>
          {(selected?.display_name ?? 'R').slice(0, 1).toUpperCase()}
        </span>
        <span className='reviewer-select__copy'>
          <span>Revisor</span>
          <strong>{selected?.display_name ?? 'Sin revisor seleccionado'}</strong>
        </span>
        <span className={`reviewer-select__chevron${open ? ' reviewer-select__chevron--open' : ''}`} aria-hidden='true'>⌄</span>
      </button>
      {open && (
        <div className='reviewer-select__menu' id={listId} role='listbox' aria-label='Revisores disponibles'>
          <button type='button' role='option' aria-selected={value === ''} onClick={() => choose('')}>
            <span className='reviewer-select__option-avatar' aria-hidden='true'>—</span>
            <span><strong>Sin revisor</strong><small>Consultar sin firmar</small></span>
            {value === '' && <span aria-hidden='true'>✓</span>}
          </button>
          {reviewers.map((item) => (
            <button
              type='button'
              role='option'
              aria-selected={value === item.identifier}
              key={item.identifier}
              onClick={() => choose(item.identifier)}
            >
              <span className='reviewer-select__option-avatar' aria-hidden='true'>{item.display_name.slice(0, 1).toUpperCase()}</span>
              <span><strong>{item.display_name}</strong><small>{item.role_label}</small></span>
              {value === item.identifier && <span aria-hidden='true'>✓</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
