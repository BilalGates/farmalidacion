import type { ReactNode } from 'react'
import { useCorporateSession } from '../auth/SessionContext'

interface WorkspaceTab {
  id: string
  label: string
  path: string
}

const WORKSPACES: Record<string, { label: string; tabs: WorkspaceTab[] }> = {
  work: {
    label: 'Trabajo',
    tabs: [
      { id: 'queue', label: 'Cola de revisión', path: '/trabajo' },
      { id: 'second', label: 'Segunda lectura', path: '/catalogo/segunda' },
      { id: 'changes', label: 'Novedades CIMA', path: '/novedades' },
    ],
  },
  data: {
    label: 'Datos',
    tabs: [
      { id: 'sources', label: 'Fuentes', path: '/datos/fuentes' },
      { id: 'imports', label: 'Importaciones', path: '/datos/importaciones' },
      { id: 'exports', label: 'Exportaciones', path: '/exportaciones' },
      { id: 'quarantine', label: 'Incidencias', path: '/datos/cuarentena' },
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
  const session = useCorporateSession()
  return (
    <div className='section-workspace'>
      <nav className='section-workspace__nav' aria-label={`Páginas de ${workspace.label}`}>
        <ul>
          {workspace.tabs.filter(tab => !session || session.capabilities.includes(tab.id === 'exports' ? 'export.read' : ['queue', 'second'].includes(tab.id) ? 'review.read' : 'sources.read')).map((tab) => (
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
