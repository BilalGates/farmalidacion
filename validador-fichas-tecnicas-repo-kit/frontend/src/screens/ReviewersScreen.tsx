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
export function ReviewersScreen() {
  const [retryKey, setRetryKey] = useState(0)
  const [identifier, setIdentifier] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<ReviewerRole>('farmaceutico')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const reviewers = useQuery(() => fetchReviewerAdmin(), [retryKey])
  const roles = useQuery(() => fetchReviewerRoles(), [])

  const refresh = () => setRetryKey((k) => k + 1)

  /** Las reglas las aplica el backend; aquí sólo se muestra lo que responde. */
  async function run(action: () => Promise<unknown>) {
    setSaving(true)
    setError(null)
    try {
      await action()
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
    })
  }

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Equipo</p>
          <h1>Revisores</h1>
          <p className='lede'>
            Quién puede firmar validaciones y con qué rol. Un revisor retirado se desactiva, no se
            borra: sus firmas anteriores siguen siendo suyas.
          </p>
        </div>
      </div>

      <form className='panel reviewer-form' onSubmit={submit}>
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
          <select value={role} onChange={(event) => setRole(event.target.value as ReviewerRole)}>
            {(roles.data ?? []).map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <button type='submit' className='button button--primary' disabled={saving}>
          Añadir revisor
        </button>
      </form>

      {error && (
        <p className='mode-banner mode-banner--warning' role='alert'>
          {error}
        </p>
      )}

      <AsyncBoundary
        loading={reviewers.loading}
        error={reviewers.error}
        empty={(reviewers.data?.length ?? 0) === 0}
        emptyTitle='No hay revisores dados de alta'
        emptyDetail='Añada al menos un farmacéutico para poder firmar validaciones.'
        onRetry={refresh}
      >
        {reviewers.data && (
          <table className='table'>
            <thead>
              <tr>
                <th scope='col'>Nombre</th>
                <th scope='col'>Identificador</th>
                <th scope='col'>Rol</th>
                <th scope='col'>Estado</th>
                <th scope='col'>
                  <span className='visually-hidden'>Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {reviewers.data.map((item) => (
                <tr key={item.identifier}>
                  <th scope='row'>{item.display_name}</th>
                  <td>
                    <code>{item.identifier}</code>
                  </td>
                  <td>
                    <select
                      aria-label={`Rol de ${item.display_name}`}
                      value={item.role}
                      disabled={saving}
                      onChange={(event) =>
                        run(() =>
                          setReviewerRole(item.identifier, event.target.value as ReviewerRole),
                        )
                      }
                    >
                      {(roles.data ?? []).map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <span className={`badge badge--${item.active ? 'validado' : 'pendiente'}`}>
                      {item.active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td>
                    <button
                      type='button'
                      className='button'
                      disabled={saving}
                      onClick={() => run(() => setReviewerActive(item.identifier, !item.active))}
                    >
                      {item.active ? 'Desactivar' : 'Reactivar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </AsyncBoundary>
    </div>
  )
}
