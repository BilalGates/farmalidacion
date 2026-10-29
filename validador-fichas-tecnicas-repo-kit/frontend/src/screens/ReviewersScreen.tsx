import { useState } from 'react'

import {
  createReviewer,
  fetchReviewerAdmin,
  fetchReviewerRoles,
  setReviewerActive,
  setReviewerRole,
} from '../api/client'
import type { ReviewerRole } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { PageHeader } from '../components/PageHeader'

/**
 * Alta, rol y activación de revisores.
 *
 * La lista vivía en una variable de entorno: dar de alta a alguien exigía
 * editar el despliegue y reiniciar el contenedor.
 *
 * Nadie se borra. Una decisión firmada debe seguir diciendo quién la puso, así
 * que un revisor retirado se desactiva: desaparece del selector de firma pero
 * sigue aquí, con sus firmas anteriores intactas y la posibilidad de volver.
 */
export function ReviewersScreen({ embedded = false }: { embedded?: boolean }) {
  const [retryKey, setRetryKey] = useState(0)
  const [identifier, setIdentifier] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<ReviewerRole>('farmaceutico')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const reviewers = useQuery(() => fetchReviewerAdmin(), [retryKey])
  const roles = useQuery(() => fetchReviewerRoles(), [retryKey])

  const refresh = () => setRetryKey((k) => k + 1)

  /** Las reglas las aplica el backend; aquí sólo se muestra lo que responde. */
  async function run(action: () => Promise<unknown>, successMessage: string) {
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      await action()
      setSuccess(successMessage)
      refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo completar la operación.')
    } finally {
      setSaving(false)
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    await run(async () => {
      await createReviewer({
        identifier: identifier.trim(),
        display_name: displayName.trim(),
        role,
      })
      setIdentifier('')
      setDisplayName('')
    }, 'Revisor añadido al equipo.')
  }

  return (
    <section className='screen reviewer-management' aria-label='Gestión de revisores'>
      <PageHeader headingLevel={embedded ? 2 : 1} eyebrow='Equipo' title='Revisores' description='Gestiona los miembros que pueden firmar validaciones y su rol.' />
      <div className='reviewer-management__layout'>
      <section className='reviewer-management__list' aria-label='Miembros del equipo'>
      <div className='reviewer-management__list-head'><h3>Miembros del equipo</h3><p className='muted'>Los revisores retirados permanecen en el historial y pueden reactivarse.</p></div>

      {error && <p className='mode-banner mode-banner--warning' role='alert'>{error}</p>}
      {success && <p className='state state--success' role='status'>{success}</p>}

      <AsyncBoundary
        loading={reviewers.loading}
        error={reviewers.error}
        empty={(reviewers.data?.length ?? 0) === 0}
        emptyTitle='No hay revisores dados de alta'
        emptyDetail='Añade al menos un farmacéutico para poder firmar validaciones.'
        onRetry={refresh}
      >
        {reviewers.data && (
          <div className='table-wrap' role='region' aria-label='Revisores; desplazamiento horizontal disponible' tabIndex={0}><table className='table'>
            <thead><tr><th scope='col'>Revisor</th><th scope='col'>Rol</th><th scope='col'>Estado</th><th scope='col'><span className='visually-hidden'>Acciones</span></th></tr></thead>
            <tbody>{reviewers.data.map((item) => (
              <tr key={item.identifier}>
                <th scope='row'><span className='reviewer-management__name'>{item.display_name}</span><code>{item.identifier}</code></th>
                <td><select aria-label={`Rol de ${item.display_name}`} value={item.role} disabled={saving || roles.loading || (roles.data?.length ?? 0) === 0} onChange={(event) => run(() => setReviewerRole(item.identifier, event.target.value as ReviewerRole), `Rol de ${item.display_name} actualizado.`)}>{(roles.data ?? []).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></td>
                <td><span className={`badge badge--${item.active ? 'validado' : 'pendiente'}`}>{item.active ? 'Activo' : 'Inactivo'}</span></td>
                <td><button type='button' className='button' disabled={saving} onClick={() => run(() => setReviewerActive(item.identifier, !item.active), `${item.display_name} ${item.active ? 'desactivado' : 'reactivado'}.`)}>{item.active ? 'Desactivar' : 'Reactivar'}</button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </AsyncBoundary>
      </section>

      <aside className='panel reviewer-management__add'>
        <h3>Añadir revisor</h3>
        <p className='muted'>La identidad y el rol se usan para atribuir nuevas validaciones.</p>

      <form className='reviewer-form' onSubmit={submit}>
        <label className='field'>
          <span className='field__label'>Identificador</span>
          <input
            value={identifier}
            required
            placeholder='mtorres'
            onChange={(event) => setIdentifier(event.target.value)}
          />
        </label>
        <label className='field'>
          <span className='field__label'>Nombre</span>
          <input
            value={displayName}
            required
            placeholder='M. Torres'
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </label>
        <label className='field'>
          <span className='field__label'>Rol</span>
          <select value={role} disabled={roles.loading || (roles.data?.length ?? 0) === 0} onChange={(event) => setRole(event.target.value as ReviewerRole)}>
            {(roles.data ?? []).map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <button type='submit' className='button button--primary' disabled={saving || roles.loading || (roles.data?.length ?? 0) === 0}>
          Añadir revisor
        </button>
      </form>
      {roles.error && <p className='state state--error' role='alert'>No se pudieron cargar los roles. <button type='button' className='button' onClick={refresh}>Reintentar</button></p>}
      </aside>
      </div>
    </section>
  )
}
