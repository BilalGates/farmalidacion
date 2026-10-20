import { fetchReviewers } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from './AsyncState'

/** Consulta del equipo sin controles de administración. */
export function TeamDirectory() {
  const reviewers = useQuery(fetchReviewers, [])

  return <section className='reviewer-management__list' aria-label='Miembros del equipo'>
    <div className='reviewer-management__list-head'>
      <h2>Miembros del equipo</h2>
      <p className='muted'>Personas activas que pueden trabajar en Farmalidación.</p>
    </div>
    <AsyncBoundary
      loading={reviewers.loading}
      error={reviewers.error}
      empty={(reviewers.data?.length ?? 0) === 0}
      emptyTitle='No hay revisores registrados'
      emptyDetail='El equipo aparecerá aquí cuando se registren revisores.'
    >
      {reviewers.data && <div className='table-wrap' role='region' aria-label='Listado de revisores; desplazamiento horizontal disponible' tabIndex={0}>
        <table className='table'>
          <thead><tr><th scope='col'>Revisor</th><th scope='col'>Rol</th></tr></thead>
          <tbody>{reviewers.data.map((item) => <tr key={item.identifier}>
            <th scope='row'><span className='reviewer-management__name'>{item.display_name}</span><code>{item.identifier}</code></th>
            <td>{item.role_label}</td>
          </tr>)}</tbody>
        </table>
      </div>}
    </AsyncBoundary>
  </section>
}
