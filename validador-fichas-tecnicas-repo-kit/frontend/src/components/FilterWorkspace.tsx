import { useState, type ReactNode } from 'react'
import { PanelLeftClose, PanelLeftOpen, SlidersHorizontal } from 'lucide-react'

interface FilterWorkspaceProps {
  title: string
  storageKey: string
  activeCount?: number
  filters: ReactNode
  children: ReactNode
  className?: string
}

function initialOpen(storageKey: string): boolean {
  try {
    return localStorage.getItem(storageKey) !== 'closed'
  } catch {
    return true
  }
}

export function FilterWorkspace({
  title,
  storageKey,
  activeCount = 0,
  filters,
  children,
  className = '',
}: FilterWorkspaceProps) {
  const [open, setOpen] = useState(() => initialOpen(storageKey))
  const panelId = `${storageKey.replace(/[^a-z0-9_-]/gi, '-')}-panel`

  function toggle() {
    setOpen((current) => {
      const next = !current
      try {
        localStorage.setItem(storageKey, next ? 'open' : 'closed')
      } catch { /* La preferencia no bloquea el uso de los filtros. */ }
      return next
    })
  }

  return (
    <div className={`filter-workspace${open ? '' : ' filter-workspace--closed'} ${className}`.trim()}>
      <aside className='filter-sidebar'>
          <section id={panelId} className='filter-panel' aria-label={title} hidden={!open}>
            <div className='filter-panel__head'>
              <div>
                <p className='eyebrow'>Refinar resultados</p>
                <h2>{title}</h2>
              </div>
              <button
                type='button'
                className='button button--icon filter-panel__toggle'
                onClick={toggle}
                aria-label='Ocultar filtros'
                aria-controls={panelId}
                aria-expanded='true'
                title='Ocultar filtros'
              >
                <PanelLeftClose size={18} aria-hidden='true' />
              </button>
            </div>
            {activeCount > 0 && <p className='filter-panel__count' aria-live='polite'>{activeCount} filtros activos</p>}
            <div className='filter-panel__body'>{filters}</div>
          </section>
        {!open && (
          <button
            type='button'
            className='button filter-panel__reopen'
            onClick={toggle}
            aria-controls={panelId}
            aria-expanded='false'
          >
            <PanelLeftOpen size={17} aria-hidden='true' />
            <SlidersHorizontal size={16} aria-hidden='true' />
            <span>Mostrar filtros</span>
            {activeCount > 0 && <span className='filter-panel__badge'>{activeCount}</span>}
          </button>
        )}
      </aside>
      <div className='filter-workspace__content'>
        {children}
      </div>
    </div>
  )
}
