import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { PanelLeftClose, PanelLeftOpen, SlidersHorizontal } from 'lucide-react'
import { useFilterLayout } from './FilterLayoutContext'

interface FilterWorkspaceProps {
  title: string
  storageKey: string
  activeCount?: number
  filters: ReactNode
  toolbar?: ReactNode
  children: ReactNode
  className?: string
  defaultOpen?: boolean
}

function initialOpen(storageKey: string, defaultOpen: boolean): boolean {
  try {
    const stored = localStorage.getItem(storageKey)
    return stored === null ? defaultOpen : stored !== 'closed'
  } catch {
    return defaultOpen
  }
}

export function FilterWorkspace({
  title,
  storageKey,
  activeCount = 0,
  filters,
  toolbar,
  children,
  className = '',
  defaultOpen = true,
}: FilterWorkspaceProps) {
  const [open, setOpen] = useState(() => initialOpen(storageKey, defaultOpen))
  const layoutId = useId()
  const reportOpen = useFilterLayout()
  useEffect(() => {
    reportOpen(layoutId, open)
    return () => reportOpen(layoutId, false)
  }, [layoutId, open, reportOpen])
  const panelId = `${storageKey.replace(/[^a-z0-9_-]/gi, '-')}-panel`
  const focusAfterToggle = useRef(false)
  const closeButton = useRef<HTMLButtonElement>(null)
  const reopenButton = useRef<HTMLButtonElement>(null)

  useLayoutEffect(() => {
    if (!focusAfterToggle.current) return
    focusAfterToggle.current = false
    ;(open ? closeButton : reopenButton).current?.focus()
  }, [open])

  function toggle() {
    focusAfterToggle.current = true
    setOpen((current) => {
      const next = !current
      try {
        localStorage.setItem(storageKey, next ? 'open' : 'closed')
      } catch { /* La preferencia no bloquea el uso de los filtros. */ }
      return next
    })
  }

  const reopen = !open && (
    <button
      ref={reopenButton}
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
  )

  return (
    <div className={`filter-workspace${open ? '' : ' filter-workspace--closed'} ${className}`.trim()}>
      {/* Con barra de búsqueda, «Mostrar filtros» se integra en ella: una sola
          fila de controles en lugar de un botón aislado encima de los resultados. */}
      {toolbar && <div className='filter-workspace__toolbar'>{toolbar && reopen}{toolbar}</div>}
      <aside className='filter-sidebar'>
          <section id={panelId} className='filter-panel' aria-label={title} hidden={!open}>
            <div className='filter-panel__head'>
              <div>
                <p className='eyebrow'>Refinar resultados</p>
                <h2>{title}</h2>
              </div>
              <button
                ref={closeButton}
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
            {activeCount > 0 && <p className='filter-panel__count' aria-live='polite'>{activeCount} {activeCount === 1 ? 'filtro activo' : 'filtros activos'}</p>}
            <div className='filter-panel__body'>{filters}</div>
          </section>
        {!toolbar && reopen}
      </aside>
      <div className='filter-workspace__content'>
        {children}
      </div>
    </div>
  )
}
