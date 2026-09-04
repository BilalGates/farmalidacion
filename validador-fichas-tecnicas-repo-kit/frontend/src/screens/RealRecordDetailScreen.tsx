import { fetchRealRecord } from '../api/client'
import type { RealRecordValue } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { OriginBadge } from '../components/OriginBadge'
import { orDash, shortHash } from '../domain/format'
import { navigate } from '../navigation'

/**
 * Ficha de un registro real, por bloques, con la procedencia de cada valor.
 *
 * La procedencia está siempre disponible pero plegada: mostrarla entera de
 * continuo enterraría el valor, y ocultarla del todo haría indistinguible un
 * dato importado de uno introducido a mano.
 */

const SOURCE_STATUS_LABELS: Record<string, string> = {
  disponible: 'Disponible',
  pendiente: 'Pendiente',
  no_disponible: 'No disponible',
}

const SOURCE_SYSTEM_LABELS: Record<string, string> = {
  master_excel: 'Maestro Excel',
  demo_showcase: 'Conjunto DEMO',
  cima: 'CIMA',
  ficha_tecnica: 'Ficha técnica',
}

/** Traduce el localizador del fragmento sin ocultar el original. */
function describeLocator(locator: string, locatorType: string): string {
  if (locatorType === 'excel_row') {
    try {
      const parsed = JSON.parse(locator) as { sheet?: string; row?: number }
      if (parsed.sheet && parsed.row) return `Hoja ${parsed.sheet}, fila ${parsed.row}`
    } catch {
      // Un localizador que no sea JSON se muestra tal cual.
    }
  }
  return locator
}

function ValueRow({ value }: { value: RealRecordValue }) {
  const empty = value.literal_value === null || value.literal_value === ''
  return (
    <tr>
      <th scope='row'>
        <code>{value.field_name}</code>
      </th>
      <td>
        {empty ? (
          <span className='muted'>Sin valor en el origen</span>
        ) : (
          value.literal_value
        )}
      </td>
      <td>
        {value.provenance.length === 0 ? (
          <span className='muted'>Sin procedencia registrada</span>
        ) : (
          <details className='disclosure disclosure--inline'>
            <summary>Ver procedencia</summary>
            <ul className='provenance'>
              {value.provenance.map((item, index) => (
                <li key={`${item.locator}-${index}`}>
                  <dl className='definition definition--compact'>
                    <div>
                      <dt>Fuente</dt>
                      <dd>
                        {item.source_system
                          ? (SOURCE_SYSTEM_LABELS[item.source_system] ?? item.source_system)
                          : '—'}
                      </dd>
                    </div>
                    <div>
                      <dt>Fichero</dt>
                      <dd>{orDash(item.source_locator ?? item.document_name)}</dd>
                    </div>
                    <div>
                      <dt>Origen del valor</dt>
                      <dd>{describeLocator(item.locator, item.locator_type)}</dd>
                    </div>
                    <div>
                      <dt>Versión</dt>
                      <dd>{orDash(item.source_version)}</dd>
                    </div>
                    <div>
                      <dt>Hash</dt>
                      <dd title={item.content_hash ?? undefined}>
                        <code>{shortHash(item.content_hash)}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>Lote</dt>
                      <dd title={item.import_batch_id ?? undefined}>
                        <code>{shortHash(item.import_batch_id)}</code>
                      </dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          </details>
        )}
      </td>
    </tr>
  )
}

export function RealRecordDetailScreen({ recordId }: { recordId: string }) {
  const { data, error, loading } = useQuery(() => fetchRealRecord(recordId), [recordId])

  return (
    <div className='screen'>
      <button type='button' className='button' onClick={() => navigate('/registros')}>
        ← Volver al listado
      </button>

      <AsyncBoundary loading={loading} error={error} empty={false} emptyTitle='' emptyDetail=''>
        {data && (
          <>
            <div className='screen__head'>
              <div>
                <p className='eyebrow'>
                  Ficha del registro <OriginBadge origin={data.origin} />
                </p>
                <h1>{orDash(data.display_name)}</h1>
                <p className='lede'>
                  Identificador <code>{orDash(data.identifier)}</code> · {data.entity_type}
                </p>
              </div>
            </div>

            {data.origin === 'demo' && (
              <p className='origin-notice origin-notice--demo'>
                Este registro procede del conjunto de demostración. Sus valores no provienen de
                los maestros y no deben usarse como evidencia clínica.
              </p>
            )}

            <section aria-label='Fuentes disponibles para este registro'>
              <h2>Fuentes de este registro</h2>
              <table className='table'>
                <thead>
                  <tr>
                    <th scope='col'>Fuente</th>
                    <th scope='col'>Estado</th>
                    <th scope='col'>Detalle</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sources.map((source) => (
                    <tr key={source.key}>
                      <th scope='row'>{source.label}</th>
                      <td>
                        <span className={`badge badge--${source.status}`}>
                          {SOURCE_STATUS_LABELS[source.status] ?? source.status}
                        </span>
                      </td>
                      <td className='muted'>{source.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            {data.blocks.length === 0 ? (
              <p className='muted'>
                Este registro no tiene ningún bloque de valores almacenado.
              </p>
            ) : (
              data.blocks.map((block) => (
                <section key={block.id} aria-label={block.block_type}>
                  <h2>
                    {block.block_type}
                    {block.ordinal > 1 && (
                      <span className='muted'> · ocurrencia {block.ordinal}</span>
                    )}
                  </h2>
                  <table className='table'>
                    <thead>
                      <tr>
                        <th scope='col'>Campo</th>
                        <th scope='col'>Valor</th>
                        <th scope='col'>Procedencia</th>
                      </tr>
                    </thead>
                    <tbody>
                      {block.values.map((value) => (
                        <ValueRow key={value.id} value={value} />
                      ))}
                    </tbody>
                  </table>
                </section>
              ))
            )}
          </>
        )}
      </AsyncBoundary>
    </div>
  )
}
