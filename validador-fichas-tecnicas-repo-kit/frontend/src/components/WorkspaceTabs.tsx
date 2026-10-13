import { useId, type ReactNode } from 'react'

interface WorkspaceTab {
  readonly id: string
  readonly label: string
  readonly content: ReactNode
}

/** Los paneles permanecen montados para conservar formularios y borradores. */
export function WorkspaceTabs({ label, tabs, active, onChange }: {
  readonly label: string
  readonly tabs: readonly WorkspaceTab[]
  readonly active: string
  readonly onChange: (id: string) => void
}) {
  const prefix = useId()
  return <div className='workspace-tabs'>
    <div className='workspace-tabs__nav' role='tablist' aria-label={label}>
      {tabs.map((tab, index) => <button key={tab.id} type='button' role='tab'
        id={`${prefix}-tab-${tab.id}`} aria-controls={`${prefix}-panel-${tab.id}`}
        aria-selected={active === tab.id} tabIndex={active === tab.id ? 0 : -1}
        onClick={() => onChange(tab.id)} onKeyDown={event => {
          const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length
            : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length
              : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null
          if (next === null) return
          event.preventDefault()
          onChange(tabs[next].id)
          event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus()
        }}>{tab.label}</button>)}
    </div>
    {tabs.map(tab => <section key={tab.id} role='tabpanel'
      id={`${prefix}-panel-${tab.id}`} aria-labelledby={`${prefix}-tab-${tab.id}`}
      className='workspace-tabs__panel' hidden={active !== tab.id}>{tab.content}</section>)}
  </div>
}
