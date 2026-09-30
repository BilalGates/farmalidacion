import type { ReactNode } from 'react'

interface WorkspaceTab {
  id: string
  label: string
  path: string
}

const WORKSPACES: Record<string, { label: string; tabs: WorkspaceTab[] }> = {
  review: {
    label: 'Revisión',
    tabs: [
      { id: 'queue', label: 'Cola de revisión', path: '/revision/cola' },
      { id: 'second-review', label: 'Segunda revisión', path: '/revision/validaciones' },
    ],
  },
  data: {
    label: 'Datos',
    tabs: [
      { id: 'sources', label: 'Fuentes', path: '/datos/fuentes' },
      { id: 'imports', label: 'Importaciones', path: '/datos/importaciones' },
      { id: 'quarantine', label: 'Cuarentena', path: '/datos/cuarentena' },
    ],
  },
}

export function SectionWorkspace({
  group,
  active,
  children,
}: {
  group: keyof typeof WORKSPACES
  active: string
  children: ReactNode
}) {
  const workspace = WORKSPACES[group]
  return (
    <div className='section-workspace'>
      <nav className='section-workspace__nav' aria-label={`Páginas de ${workspace.label}`}>
        <ul>
          {workspace.tabs.map((tab) => (
            <li key={tab.id}>
              <a href={`#${tab.path}`} aria-current={active === tab.id ? 'page' : undefined}>
                {tab.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      {children}
    </div>
  )
}
