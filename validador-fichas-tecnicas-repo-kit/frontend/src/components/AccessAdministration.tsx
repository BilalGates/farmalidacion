import { useState } from 'react'

import { fetchAccessOverview } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from './AsyncState'

const CAPABILITY_LABELS: Record<string, string> = {
  'catalog.read': 'Consultar catálogo',
  'catalog.maintain': 'Mantener catálogo',
  'sources.read': 'Consultar fuentes',
  'sources.manage': 'Gestionar fuentes',
  'review.read': 'Consultar trabajo',
  'review.write': 'Validar',
  'review.reconcile': 'Conciliar segunda lectura',
  'export.read': 'Consultar exportaciones',
  'export.create': 'Crear exportaciones',
  'audit.read': 'Consultar auditoría',
  'team.manage': 'Administrar equipo',
}

export function AccessAdministration() {
  const [retryKey, setRetryKey] = useState(0)
  const access = useQuery(() => fetchAccessOverview(), [retryKey])
  return <section className='screen access-administration' aria-labelledby='access-administration-title'>
    <header className='screen__head'>
      <div>
        <p className='eyebrow'>Acceso corporativo</p>
        <h2 id='access-administration-title'>Usuarios y permisos</h2>
        <p className='lede'>Las cuentas, contraseñas y asignaciones de rol se administran en Microsoft Entra ID. Aquí puedes comprobar los vínculos y capacidades configurados para la aplicación.</p>
      </div>
    </header>
    <AsyncBoundary loading={access.loading} error={access.error} empty={false} emptyTitle='' emptyDetail='' onRetry={() => setRetryKey(value => value + 1)}>
      {access.data && <div className='access-administration__grid'>
        <section className='panel access-administration__accounts' aria-label='Vínculos configurados'>
          <h3>Vínculos configurados</h3>
          <p className='muted'>Un vínculo se sella al primer acceso verificado. El acceso requiere además un rol asignado en Entra y un revisor activo.</p>
          {access.data.accounts.length ? <ul className='access-administration__list'>
            {access.data.accounts.map(account => <li key={account.object_id}>
              <span><strong>{account.display_name}</strong><small>{account.reviewer_identifier}</small><code title='Identificador de objeto de Microsoft Entra'>{account.object_id}</code></span>
              <span className={`badge badge--${account.active ? 'validado' : 'pendiente'}`}>{account.active ? 'Activo' : 'Inactivo'}</span>
              <small>{account.linked ? 'Vínculo verificado' : 'Pendiente del primer acceso'}</small>
            </li>)}
          </ul> : <p className='state state--empty'>No hay cuentas vinculadas en la configuración.</p>}
        </section>
        <section className='panel access-administration__roles' aria-label='Roles corporativos'>
          <h3>Roles corporativos</h3>
          <p className='muted'>Los permisos de aplicación proceden del rol asignado en Entra; son independientes del rol clínico del revisor.</p>
          <ul className='access-administration__list'>
            {access.data.roles.map(role => <li key={role.name}>
              <strong>{role.name}</strong>
              <span className='access-administration__capabilities'>{role.capabilities.map(capability => <span key={capability} className='chip' title={capability}>{CAPABILITY_LABELS[capability] ?? capability}</span>)}</span>
            </li>)}
          </ul>
        </section>
      </div>}
    </AsyncBoundary>
  </section>
}
