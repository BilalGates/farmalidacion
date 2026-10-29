import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'

/**
 * Barra de filtros única de la aplicación.
 *
 * Todas las pantallas filtran igual: una fila encima de los resultados, con
 * cada filtro como una píldora que muestra su valor («Libro: Todos») y se
 * aplica al momento. Sin panel lateral, sin botón «Aplicar» y sin plegar la
 * navegación. Cada control es un elemento nativo (select, checkbox, input)
 * para conservar teclado y lectores de pantalla.
 */
export function FilterBar({ label, search, activeCount = 0, onClear, clearable = false, aside, children }: {
  readonly label: string
  /** Buscador y orden, en la primera fila. */
  readonly search?: ReactNode
  readonly activeCount?: number
  readonly onClear?: () => void
  /** Ofrece limpiar aunque no haya filtros aplicados (p. ej. una búsqueda escrita sin lanzar). */
  readonly clearable?: boolean
  /** Controles que no son filtros (cambio de vista, actualizar), al final de la fila. */
  readonly aside?: ReactNode
  readonly children?: ReactNode
}) {
  return (
    <section className='filter-bar' aria-label={label}>
      {/* Con buscador, los controles de vista van en su fila: los filtros
          quedan juntos y sin saltos de línea. */}
      {search && <div className='filter-bar__search'>{search}{aside && <div className='filter-bar__aside'>{aside}</div>}</div>}
      {(children || (aside && !search)) && <div className='filter-bar__row'>
        <div className='filter-bar__filters' role='group' aria-label='Filtros'>
          {children}
          {onClear && (activeCount > 0 || clearable) && <button type='button' className='filter-bar__clear' onClick={onClear}>
            Limpiar filtros{activeCount > 0 ? ` · ${activeCount}` : ''}
          </button>}
        </div>
        {aside && !search && <div className='filter-bar__aside'>{aside}</div>}
      </div>}
    </section>
  )
}

interface Option { readonly value: string; readonly label: string; readonly disabled?: boolean }

/** Un valor entre varios. La opción vacía es «sin filtrar». */
export function FilterSelect({ label, name, value, options, onChange, title }: {
  /** Texto corto visible en la píldora. */
  readonly label: string
  /** Nombre accesible completo; por defecto, el visible. */
  readonly name?: string
  readonly value: string
  readonly options: readonly Option[]
  readonly onChange: (value: string) => void
  readonly title?: string
}) {
  return (
    <label className='filter-pill' data-active={value !== '' && value !== 'all' ? 'true' : undefined} title={title}>
      <span className='filter-pill__label'>{label}</span>
      <select aria-label={name ?? label} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(option => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}
      </select>
      <ChevronDown size={14} aria-hidden='true' />
    </label>
  )
}

/** Varias opciones a la vez, en un menú que se despliega desde la píldora. */
export function FilterChecks({ label, values, options, onToggle, hint }: {
  readonly label: string
  readonly values: readonly string[]
  readonly options: readonly Option[]
  readonly onToggle: (value: string) => void
  readonly hint?: string
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  const summary = values.length === 0 ? 'Todas' : values.length === 1 ? options.find(option => option.value === values[0])?.label ?? values[0] : `${values.length} elegidas`
  return (
    <div className='filter-pill filter-pill--menu' ref={root} data-active={values.length > 0 ? 'true' : undefined}
      onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false) }}>
      <button type='button' className='filter-pill__trigger' aria-expanded={open} onClick={() => setOpen(current => !current)}>
        <span className='filter-pill__label'>{label}</span>
        <span className='filter-pill__value'>{summary}</span>
        <ChevronDown size={14} aria-hidden='true' />
      </button>
      {open && <fieldset className='filter-pill__menu'>
        <legend className='visually-hidden'>{label}</legend>
        {options.map(option => <label key={option.value}>
          <input type='checkbox' checked={values.includes(option.value)} onChange={() => onToggle(option.value)} />
          {option.label}
        </label>)}
        {hint && <small>{hint}</small>}
      </fieldset>}
    </div>
  )
}

/** Texto libre: se aplica al pulsar Intro o al salir del campo, no a cada tecla. */
export function FilterText({ label, value, placeholder, onCommit }: {
  readonly label: string
  readonly value: string
  readonly placeholder?: string
  readonly onCommit: (value: string) => void
}) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  const commit = () => { if (draft.trim() !== value) onCommit(draft.trim()) }
  return (
    <label className='filter-pill filter-pill--text' data-active={value ? 'true' : undefined}>
      <span className='filter-pill__label'>{label}</span>
      <input aria-label={label} value={draft} placeholder={placeholder}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); commit() } }} />
    </label>
  )
}

/** Sí o no. */
export function FilterToggle({ label, checked, onChange }: {
  readonly label: string
  readonly checked: boolean
  readonly onChange: (checked: boolean) => void
}) {
  return (
    <label className='filter-pill filter-pill--toggle' data-active={checked ? 'true' : undefined}>
      <input type='checkbox' checked={checked} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  )
}
