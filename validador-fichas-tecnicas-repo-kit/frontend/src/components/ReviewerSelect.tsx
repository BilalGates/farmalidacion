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
  const options = [{ identifier: '', display_name: 'Sin revisor' }, ...reviewers]
  const [activeIndex, setActiveIndex] = useState(0)
  const trigger = useRef<HTMLButtonElement>(null)

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
    trigger.current?.focus()
  }

  return (
    <div className='reviewer-select' ref={root}>
      <button
        ref={trigger}
        type='button'
        className='reviewer-select__trigger'
        role='combobox'
        aria-label='Revisor que firma las decisiones'
        aria-controls={listId}
        aria-expanded={open}
        aria-haspopup='listbox'
        aria-activedescendant={open ? `${listId}-option-${activeIndex}` : undefined}
        onClick={() => { setActiveIndex(Math.max(0, options.findIndex((item) => item.identifier === value))); setOpen((current) => !current) }}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && open) { event.preventDefault(); setOpen(false) }
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            setActiveIndex((current) => open ? (current + (event.key === 'ArrowDown' ? 1 : options.length - 1)) % options.length : Math.max(0, options.findIndex((item) => item.identifier === value)))
            setOpen(true)
          }
          if (open && (event.key === 'Home' || event.key === 'End')) { event.preventDefault(); setActiveIndex(event.key === 'Home' ? 0 : options.length - 1) }
          if (open && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); choose(options[activeIndex].identifier) }
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
          <button id={`${listId}-option-0`} tabIndex={-1} type='button' role='option' aria-selected={value === ''} onClick={() => choose('')}>
            <span className='reviewer-select__option-avatar' aria-hidden='true'>—</span>
            <span><strong>Sin revisor</strong><small>Consultar sin firmar</small></span>
            {value === '' && <span aria-hidden='true'>✓</span>}
          </button>
          {reviewers.map((item, index) => (
            <button
              id={`${listId}-option-${index + 1}`}
              tabIndex={-1}
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
