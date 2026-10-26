import { useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  closeLocalConnector,
  fetchNomenclatorChanges,
  fetchNomenclatorHistory,
  fetchNomenclatorReconciliation,
  fetchNomenclatorRows,
  fetchNomenclatorSnapshot,
  probeLocalConnector,
  synchronizePersonalNomenclator,
} from '../api/client'
import type { LocalConnectorStatus, LocalNomenclatorConnection } from '../api/client'
import type { NomenclatorChanges } from '../api/types'
import { useQuery } from '../api/useQuery'
import { useCorporateSession } from '../auth/SessionContext'
import { formatDateTime, shortHash } from '../domain/format'

/**
 * «Mi Nomenclátor»: la copia persistida se consulta siempre desde la API; el
 * conector local sólo interviene para leer una versión nueva de SQL Server.
 */

type View = 'none' | 'data' | 'history' | 'connection'
type Stage = 'idle' | 'reading' | 'saving'

const CONNECTION_KEY = 'farmalidacion.nomenclator.connection'
const DEFAULT_CONNECTION: LocalNomenclatorConnection = {
  server: 'localhost', port: 0, database: 'DICCIONARIOS', auth: 'windows',
  username: '', password: '', encrypt: true, trust_server_certificate: false,
}

const MATCH_LABELS = {
  exacta: 'CN en catálogo',
  ambigua: 'CN ambiguo',
  sin_correspondencia: 'Sin correspondencia',
} as const

const number = (value: number) => value.toLocaleString('es-ES')

function storedConnection(): LocalNomenclatorConnection {
  try {
    const raw = localStorage.getItem(CONNECTION_KEY)
    // Nunca se guarda la contraseña: sólo parámetros no secretos.
    return raw ? { ...DEFAULT_CONNECTION, ...JSON.parse(raw) as Partial<LocalNomenclatorConnection>, password: '' } : DEFAULT_CONNECTION
  } catch { return DEFAULT_CONNECTION }
}

function rememberConnection(connection: LocalNomenclatorConnection) {
  try {
    localStorage.setItem(CONNECTION_KEY, JSON.stringify({ ...connection, password: undefined }))
  } catch { /* Preferencia local opcional. */ }
}

function ChangesSummary({ changes }: { changes: NomenclatorChanges }) {
  if (changes.previous_sha256 === null) {
    return <p className='nomenclator-changes'>Primera versión: <strong>{number(changes.added)}</strong> registros.</p>
  }
  if (!changes.added && !changes.removed && !changes.modified) {
    return <p className='nomenclator-changes'>Sin diferencias de contenido frente a la versión anterior.</p>
  }
  return <div className='nomenclator-changes'>
    <dl className='nomenclator-changes__counts'>
      <div><dt>Nuevos</dt><dd>{number(changes.added)}</dd></div>
      <div><dt>Modificados</dt><dd>{number(changes.modified)}</dd></div>
      <div><dt>Ya no figuran</dt><dd>{number(changes.removed)}</dd></div>
    </dl>
    {[['Nuevos', changes.sample_added, changes.added], ['Modificados', changes.sample_modified, changes.modified], ['Ya no figuran', changes.sample_removed, changes.removed]]
      .filter(([, sample]) => (sample as string[]).length > 0)
      .map(([label, sample, total]) => <p key={label as string} className='muted'>
        {label as string}: {(sample as string[]).join(', ')}{(total as number) > (sample as string[]).length ? '…' : ''}
      </p>)}
  </div>
}

function DataView() {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const rows = useQuery(() => fetchNomenclatorRows(query, offset), [query, offset])
  const summary = useQuery(fetchNomenclatorReconciliation, [])
  const page = rows.data
  return <div className='nomenclator-view' id='nomenclator-view-data'>
    {summary.data?.available && <dl className='nomenclator-match'>
      <div><dt>CN con presentación en catálogo</dt><dd>{number(summary.data.exact)}</dd></div>
      <div><dt>CN ambiguos</dt><dd>{number(summary.data.ambiguous)}</dd></div>
      <div><dt>Sin correspondencia</dt><dd>{number(summary.data.nomenclator_without_catalog)}</dd></div>
      <div><dt>Catálogo sin Nomenclátor</dt><dd>{number(summary.data.catalog_without_nomenclator)}</dd></div>
    </dl>}
    <p className='muted'>La correspondencia se establece sólo por igualdad exacta del código nacional. No se consolida ningún registro ni se modifica el catálogo.</p>
    <form className='nomenclator-search' role='search' onSubmit={(event) => { event.preventDefault(); setOffset(0); setQuery(draft.trim()) }}>
      <label className='field'><span>Buscar por CN, n.º de registro, ATC o principio activo</span>
        <input type='search' maxLength={120} value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
      <button className='button button--secondary' type='submit'>Buscar</button>
    </form>
    {rows.error && <p role='alert'>{rows.error}</p>}
    {page && page.available && <>
      <p className='muted' aria-live='polite'>{number(page.total)} registros{query ? ` para «${query}»` : ''}.</p>
      <div className='nomenclator-table'><table className='data-table'>
        <thead><tr><th>CN</th><th>N.º registro</th><th>Principio activo declarado</th><th>ATC</th><th>Estado</th><th>Catálogo</th></tr></thead>
        <tbody>{page.items.map((row) => <tr key={row.code}>
          <td><code>{row.code}</code></td><td>{row.values.nro_definitivo ?? '—'}</td>
          <td>{row.values.principioactivo ?? '—'}</td><td>{row.values.cod_atc ?? '—'}</td>
          <td>{row.values.estado ?? '—'}</td>
          <td><span className={`badge${row.catalog_match === 'exacta' ? ' badge--confirmado' : row.catalog_match === 'ambigua' ? ' badge--warning' : ''}`}>{MATCH_LABELS[row.catalog_match]}</span></td>
        </tr>)}</tbody>
      </table></div>
      <div className='nomenclator-pager'>
        <button type='button' className='button button--secondary' disabled={offset === 0 || rows.loading} onClick={() => setOffset((value) => Math.max(0, value - 25))}>Anterior</button>
        <span className='muted'>{page.total ? `${number(offset + 1)}–${number(Math.min(offset + 25, page.total))}` : '0'} de {number(page.total)}</span>
        <button type='button' className='button button--secondary' disabled={offset + 25 >= page.total || rows.loading} onClick={() => setOffset((value) => value + 25)}>Siguiente</button>
      </div>
    </>}
  </div>
}

function HistoryView({ refresh }: { refresh: number }) {
  const { data, error } = useQuery(fetchNomenclatorHistory, [refresh])
  const [selected, setSelected] = useState<number | null>(null)
  const changes = useQuery(
    () => selected === null ? Promise.resolve(null) : fetchNomenclatorChanges(selected), [selected],
  )
  if (error) return <p role='alert'>{error}</p>
  if (!data) return <p className='muted'>Cargando historial…</p>
  if (!data.length) return <p className='muted'>Todavía no hay sincronizaciones.</p>
  return <div className='nomenclator-view' id='nomenclator-view-history'>
    <p className='muted'>Cada sincronización queda registrada. Las versiones anteriores se conservan y no se sobrescriben.</p>
    <ol className='nomenclator-history'>{data.map((version) => <li key={version.version_id}>
      <div>
        <strong>{formatDateTime(version.synced_at)}</strong>
        {version.current && <span className='badge badge--confirmado'>Vigente</span>}
        <p className='muted'>{number(version.row_count)} registros · origen {version.latest_source_date ?? 'sin fecha'} · <code>{shortHash(version.sha256)}</code>{version.changed ? '' : ' · mismo contenido que la anterior'}</p>
      </div>
      {version.changed && <button type='button' className='button button--secondary' aria-expanded={selected === version.version_id} onClick={() => setSelected((value) => value === version.version_id ? null : version.version_id)}>
        {selected === version.version_id ? 'Ocultar cambios' : 'Ver cambios'}
      </button>}
      {selected === version.version_id && (changes.data ? <ChangesSummary changes={changes.data} /> : changes.error ? <p role='alert'>{changes.error}</p> : <p className='muted'>Comparando versiones…</p>)}
    </li>)}</ol>
  </div>
}

export function NomenclatorSourcePanel() {
  const account = useCorporateSession()
  const [refresh, setRefresh] = useState(0)
  const { data: snapshot, error: snapshotError, loading } = useQuery(fetchNomenclatorSnapshot, [refresh])
  const [connector, setConnector] = useState<LocalConnectorStatus | null>(null)
  const [checking, setChecking] = useState(false)
  const [view, setView] = useState<View>('none')
  const [connection, setConnection] = useState<LocalNomenclatorConnection>(storedConnection)
  const [stage, setStage] = useState<Stage>('idle')
  const [result, setResult] = useState<{ message: string; changes: NomenclatorChanges | null } | null>(null)
  const [error, setError] = useState('')

  const check = useCallback(async () => {
    setChecking(true)
    setConnector(await probeLocalConnector())
    setChecking(false)
  }, [])
  useEffect(() => { if (account) void check() }, [account, check])

  function change<K extends keyof LocalNomenclatorConnection>(key: K, value: LocalNomenclatorConnection[K]) {
    setConnection((current) => ({ ...current, [key]: value }))
  }
  function toggle(next: View) { setView((current) => current === next ? 'none' : next) }

  async function sync(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    setError(''); setResult(null)
    rememberConnection(connection)
    try {
      const imported = await synchronizePersonalNomenclator(connection, setStage)
      // Sólo se informa de éxito tras la respuesta de la API: copia verificada y guardada.
      setResult(imported.changed
        ? { message: `Datos actualizados: ${number(imported.row_count)} registros verificados y guardados.`, changes: imported.changes ?? null }
        : { message: 'Tus datos ya estaban al día: el contenido coincide con la versión vigente.', changes: null })
      setRefresh((value) => value + 1)
      if (view === 'connection') setView('none')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo actualizar Nomenclátor.')
      void check()
    } finally {
      setConnection((current) => ({ ...current, password: '' }))
      setStage('idle')
    }
  }

  async function close() {
    setError('')
    try { await closeLocalConnector(); setConnector({ reachable: false, busy: false, version: null }) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo cerrar el conector.') }
  }

  const available = Boolean(snapshot?.available)
  const busy = stage !== 'idle'
  const needsPassword = connection.auth === 'sql' && !connection.password
  const canUpdate = Boolean(account && connector?.reachable && !connector.busy && !busy && !needsPassword)
  const connectorLabel = checking ? 'Comprobando…'
    : connector?.reachable ? (connector.busy ? 'Leyendo datos' : 'Conectado') : 'No detectado'

  return <section className='panel source-connector source-connector--nomenclator nomenclator-source' aria-label='Mi Nomenclátor' aria-busy={busy}>
    <div className='panel__head'>
      <div><p className='eyebrow'>Fuente personal · SQL Server</p><h2>Mi Nomenclátor</h2></div>
      <span className={`badge${available ? ' badge--confirmado' : ''}`}>{loading && !snapshot ? 'Cargando…' : available ? 'Datos disponibles' : 'Sin datos'}</span>
    </div>

    {snapshotError && <p role='alert'>{snapshotError}</p>}
    {available && snapshot ? <dl className='nomenclator-facts'>
      <div><dt>Registros</dt><dd>{number(snapshot.row_count)}</dd></div>
      <div><dt>Fecha de origen</dt><dd>{snapshot.latest_source_date ?? 'No indicada'}</dd></div>
      <div><dt>Última actualización</dt><dd>{snapshot.synced_at ? formatDateTime(snapshot.synced_at) : '—'}</dd></div>
      <div><dt>Versión</dt><dd><code title={snapshot.sha256 ?? ''}>{shortHash(snapshot.sha256 ?? '')}</code>{snapshot.version_count ? ` · ${number(snapshot.version_count)} sincr.` : ''}</dd></div>
    </dl> : !loading && <p className='source-connector__description'>Aún no has importado tu Nomenclátor. Al hacerlo, la copia queda guardada en Farmalidación y asociada a tu cuenta.</p>}
    {available && <p className='source-connector__description'>Tu copia está guardada en Farmalidación. Puedes consultarla y usarla en el catálogo aunque el conector esté cerrado.</p>}

    {!account ? <p className='note'>Para actualizar tu Nomenclátor necesitas una sesión corporativa.</p> : <>
      <div className='nomenclator-connector' role='status' aria-live='polite'>
        <span className={`nomenclator-connector__dot${connector?.reachable ? ' is-on' : ''}`} aria-hidden='true' />
        <span>Conector de este equipo: <strong>{connectorLabel}</strong></span>
        <button type='button' className='button button--ghost' onClick={() => void check()} disabled={checking || busy}>Comprobar</button>
        {connector?.reachable && !busy && <button type='button' className='button button--ghost' onClick={() => void close()}>Cerrar conector</button>}
      </div>
      {connector && !connector.reachable && !checking && <details className='source-connector__requirements' open={!available}>
        <summary>Cómo abrir el conector para actualizar</summary>
        <ol>
          <li><a href='/downloads/conector-nomenclator.zip' download>Descarga el conector para Windows</a> y descomprímelo (sólo la primera vez).</li>
          <li>Abre «iniciar-conector.cmd». La primera vez te pedirá la dirección de Farmalidación y la recordará.</li>
          <li>Si el navegador pide acceso a la red local, permítelo y pulsa «Comprobar».</li>
        </ol>
        <p className='muted'>Sólo hace falta para traer una versión nueva. Al terminar puedes cerrarlo.</p>
      </details>}

      <div className='source-actions nomenclator-actions'>
        <button type='button' className='button button--primary' disabled={!canUpdate} onClick={() => void sync()}
          title={!connector?.reachable ? 'Abre el conector en este equipo para actualizar.' : needsPassword ? 'Introduce la contraseña en «Configurar conexión».' : undefined}>
          {stage === 'reading' ? 'Leyendo SQL Server…' : stage === 'saving' ? 'Verificando y guardando…' : 'Actualizar datos'}
        </button>
        {available && <button type='button' className='button button--secondary' aria-expanded={view === 'data'} aria-controls='nomenclator-view-data' onClick={() => toggle('data')}>Ver información</button>}
        {available && <button type='button' className='button button--secondary' aria-expanded={view === 'history'} aria-controls='nomenclator-view-history' onClick={() => toggle('history')}>Historial</button>}
        <button type='button' className='button button--ghost' aria-expanded={view === 'connection'} aria-controls='nomenclator-view-connection' onClick={() => toggle('connection')}>Configurar conexión</button>
      </div>
      <p className='muted nomenclator-target'>{connection.server}{connection.port ? `:${connection.port}` : ''} · {connection.database} · {connection.auth === 'windows' ? 'sesión de Windows' : `usuario ${connection.username || 'SQL Server'}`}</p>
    </>}

    {busy && <p role='status' className='nomenclator-progress'>{stage === 'reading' ? 'Leyendo dbo.nomenclatur en este equipo. No cierres el conector.' : 'Comprobando columnas, códigos y hash antes de publicar la nueva versión. La versión vigente sigue disponible.'}</p>}
    {result && <div role='status' className='nomenclator-result'><p>{result.message}</p>{result.changes && <ChangesSummary changes={result.changes} />}</div>}
    {error && <p role='alert'>{error} La versión vigente no se ha modificado.</p>}

    {view === 'connection' && account && <form id='nomenclator-view-connection' className='source-connector__form' onSubmit={(event) => void sync(event)}>
      <p className='muted'>«localhost» se refiere a este ordenador. Se lee únicamente dbo.nomenclatur, en modo lectura. La contraseña no se guarda ni se envía a Farmalidación.</p>
      <div className='source-connection-grid'>
        <label className='field'><span>Servidor SQL Server</span><input required value={connection.server} onChange={(event) => change('server', event.target.value)} /></label>
        <label className='field'><span>Puerto (0: automático)</span><input required type='number' min={0} max={65535} value={connection.port} onChange={(event) => change('port', Number(event.target.value))} /></label>
        <label className='field'><span>Base de datos</span><input required value={connection.database} onChange={(event) => change('database', event.target.value)} /></label>
        <label className='field'><span>Cómo te conectas</span><select value={connection.auth} onChange={(event) => change('auth', event.target.value as 'windows' | 'sql')}><option value='windows'>Mi sesión de Windows</option><option value='sql'>Usuario de SQL Server</option></select></label>
        {connection.auth === 'sql' && <><label className='field'><span>Usuario SQL Server</span><input required value={connection.username} onChange={(event) => change('username', event.target.value)} /></label><label className='field'><span>Contraseña SQL Server</span><input required type='password' autoComplete='off' value={connection.password} onChange={(event) => change('password', event.target.value)} /></label></>}
      </div>
      <label className='field field--inline'><input type='checkbox' checked={connection.encrypt} onChange={(event) => change('encrypt', event.target.checked)} /><span>Cifrar la conexión con SQL Server (recomendado)</span></label>
      <label className='field field--inline'><input type='checkbox' checked={connection.trust_server_certificate} onChange={(event) => change('trust_server_certificate', event.target.checked)} /><span>Confiar en el certificado de este servidor (solo si lo conozco)</span></label>
      <button className='button button--primary' type='submit' disabled={!canUpdate || !connection.server.trim() || !connection.database.trim()}>Guardar y actualizar datos</button>
    </form>}
    {view === 'data' && available && <DataView key={snapshot?.sha256 ?? ''} />}
    {view === 'history' && available && <HistoryView refresh={refresh} />}
  </section>
}
