import { useEffect, useState, type FormEvent } from 'react'

import { fetchDatabaseInfo, fetchNomenclatorConnection, fetchSource, fetchSources, importMasterWorkbook, previewMasterWorkbook, saveNomenclatorConnection, testNomenclatorConnection, updateSource } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { PageHeader } from '../components/PageHeader'
import { formatDateTime, orDash, shortHash } from '../domain/format'
import { openCatalogSource } from '../domain/catalogSourceNavigation'
import type { CatalogSourceWorkbook, NomenclatorConnectionFields } from '../api/types'

/** Perfiles de los tres libros de origen; el estado cargado procede de la API. */

const SOURCE_TYPE_LABELS: Record<string, string> = {
  master_excel: 'Maestro Excel',
  demo_showcase: 'Conjunto DEMO',
  cima: 'CIMA',
  ficha_tecnica: 'Ficha técnica',
}

const STATUS_LABELS: Record<string, string> = {
  disponible: 'Disponible',
  con_errores: 'Con errores',
  sin_datos: 'Sin datos',
}

const WORKBOOK_PREVIEWS: Record<string, {
  view: CatalogSourceWorkbook
  title: string
  description: string
  action: string
  sheets: Record<string, string>
}> = {
  'Especialidades-CargaMaster190626.xlsx': {
    view: 'especialidades', title: 'Especialidades y presentaciones',
    description: 'Cada registro principal identifica una presentación mediante su Código Nacional. Los excipientes se conservan como ocurrencias separadas.',
    action: 'Explorar presentaciones',
    sheets: { General: 'Presentaciones y códigos nacionales', Excipientes: 'Excipientes por presentación' },
  },
  'Medicamento-cargaMaster25062026.xlsx': {
    view: 'medicamentos', title: 'Medicamentos',
    description: 'La ficha del medicamento conserva composición, indicaciones, vías y enlaces en hojas y ocurrencias distintas.',
    action: 'Explorar medicamentos',
    sheets: {
      General: 'Identidad y datos generales', Composicion: 'Componentes y cantidades',
      Indicacion: 'Indicaciones', Frecuencia: 'Frecuencias', Via: 'Vías de administración',
      Prescripcion: 'Prescripción', Links: 'Enlaces relacionados',
    },
  },
  'PrincipioActivoCargaMaster-22062026.xlsx': {
    view: 'principios_activos', title: 'Principios activos',
    description: 'La identidad del principio activo y sus datos complementarios se consultan por hoja sin mezclarlos con medicamentos o presentaciones.',
    action: 'Explorar principios activos',
    sheets: {
      General: 'Identidad del principio activo', Frecuencia: 'Frecuencias',
      Via: 'Vías de administración', ConsejosAdministracion: 'Consejos de administración',
      DatosAnaliticos: 'Datos analíticos',
    },
  },
}

function MasterUpload({ kind, onImported }: { kind: CatalogSourceWorkbook; onImported: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof previewMasterWorkbook>> | null>(null)
  const [actor, setActor] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function analyze() {
    if (!file) return
    setBusy(true); setError(''); setMessage('')
    try { setPreview(await previewMasterWorkbook(kind, file)) }
    catch (cause) { setPreview(null); setError(cause instanceof Error ? cause.message : 'No se pudo analizar el Excel.') }
    finally { setBusy(false) }
  }

  async function importFile() {
    if (!file || !preview) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await importMasterWorkbook(kind, file, { sha256: preview.sha256, actor_id: actor, reason })
      setMessage(result.created ? 'Libro importado. Consulte el lote en Importaciones.' : 'El mismo contenido ya estaba importado.')
      setFile(null); setPreview(null); setReason(''); onImported()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo importar el Excel.') }
    finally { setBusy(false) }
  }

  return <div className='source-upload'>
    <label className='field'><span>Archivo XLSX</span><input type='file' accept='.xlsx' onChange={(event) => {
      setFile(event.target.files?.[0] ?? null); setPreview(null); setError(''); setMessage('')
    }} /></label>
    <button className='button' type='button' disabled={!file || busy} onClick={() => void analyze()}>{busy ? 'Analizando…' : 'Analizar archivo'}</button>
    {preview && <>
      <p>{preview.data_rows.toLocaleString('es-ES')} filas · {preview.sheets.length} hojas · SHA-256 <code>{shortHash(preview.sha256)}</code></p>
      {preview.blocked_reason && <p role='note'>{preview.blocked_reason}</p>}
      <label className='field'><span>Responsable</span><input maxLength={80} value={actor} onChange={(event) => setActor(event.target.value)} /></label>
      <label className='field'><span>Motivo</span><input maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <button className='button button--primary' type='button' disabled={busy || !preview.can_import || !actor.trim() || !reason.trim()} onClick={() => void importFile()}>Confirmar importación</button>
    </>}
    {error && <p role='alert'>{error}</p>}{message && <p role='status'>{message}</p>}
  </div>
}

function NomenclatorConnection() {
  const [refresh, setRefresh] = useState(0)
  const { data, error, loading } = useQuery(fetchNomenclatorConnection, [refresh])
  const [fields, setFields] = useState<NomenclatorConnectionFields>({ host: '', port: 1433, database_name: '', username: '' })
  const [password, setPassword] = useState('')
  const [actor, setActor] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [failure, setFailure] = useState('')

  useEffect(() => { if (data?.configured) setFields({
    host: data.host ?? '', port: data.port, database_name: data.database_name ?? '', username: data.username ?? '',
  }) }, [data])
  function field<K extends keyof NomenclatorConnectionFields>(key: K, value: NomenclatorConnectionFields[K]) {
    setFields((current) => ({ ...current, [key]: value }))
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setFailure(''); setFeedback('')
    try {
      await saveNomenclatorConnection({ ...fields, actor_id: actor, reason })
      setReason(''); setFeedback('Configuración guardada. La contraseña no se ha almacenado.'); setRefresh((value) => value + 1)
    } catch (cause) { setFailure(cause instanceof Error ? cause.message : 'No se pudo guardar la configuración.') }
    finally { setBusy(false) }
  }
  async function probe() {
    setBusy(true); setFailure(''); setFeedback('')
    try {
      const result = await testNomenclatorConnection({ ...fields, password })
      setFeedback(`${result.message} Base: ${result.database_name}.`)
    } catch (cause) { setFailure(cause instanceof Error ? cause.message : 'No se pudo probar la conexión.') }
    finally { setPassword(''); setBusy(false) }
  }

  return <section className='panel source-connector' aria-label='Conexión con Nomenclátor'>
    <div className='panel__head'><div><p className='eyebrow'>Base de datos</p><h2>Nomenclátor</h2></div><span className='badge'>{data?.configured ? 'Configurada' : 'Sin configurar'}</span></div>
    <p>La prueba SQL Server sólo consulta el nombre de la base; aún no importa registros. Utilice una cuenta con permisos de lectura.</p>
    {loading && <p>Cargando configuración…</p>}{error && <p role='alert'>{error}</p>}
    <form onSubmit={(event) => void save(event)}>
      <div className='source-connection-grid'>
        <label className='field'><span>Servidor</span><input required value={fields.host} onChange={(event) => field('host', event.target.value)} placeholder='servidor o IP' /></label>
        <label className='field'><span>Puerto</span><input required type='number' min={1} max={65535} value={fields.port} onChange={(event) => field('port', Number(event.target.value))} /></label>
        <label className='field'><span>Base de datos</span><input required value={fields.database_name} onChange={(event) => field('database_name', event.target.value)} /></label>
        <label className='field'><span>Usuario SQL Server</span><input required autoComplete='username' value={fields.username} onChange={(event) => field('username', event.target.value)} /></label>
      </div>
      <label className='field'><span>Contraseña para probar la conexión</span><input type='password' autoComplete='off' value={password} onChange={(event) => setPassword(event.target.value)} placeholder={data?.server_password_configured ? 'Secreto configurado en el servidor' : 'No se guarda'} /></label>
      <div className='source-actions'><button type='button' className='button' disabled={busy || !fields.host || !fields.database_name || !fields.username || (!password && !data?.server_password_configured)} onClick={() => void probe()}>Probar conexión</button></div>
      <label className='field'><span>Responsable del cambio</span><input required maxLength={80} value={actor} onChange={(event) => setActor(event.target.value)} /></label>
      <label className='field'><span>Motivo</span><input required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <button type='submit' className='button button--primary' disabled={busy}>Guardar configuración</button>
    </form>
    {feedback && <p role='status'>{feedback}</p>}{failure && <p role='alert'>{failure}</p>}
  </section>
}

function SourceDetail({ id, onClose, onSaved }: { id: string; onClose: () => void; onSaved: () => void }) {
  const [displayName, setDisplayName] = useState('')
  const [actorId, setActorId] = useState('')
  const [reason, setReason] = useState('')
  const [active, setActive] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [saved, setSaved] = useState(false)
  const [detailRefresh, setDetailRefresh] = useState(0)
  const [workbookFile, setWorkbookFile] = useState<File | null>(null)
  const [workbookPreview, setWorkbookPreview] = useState<Awaited<ReturnType<typeof previewMasterWorkbook>> | null>(null)
  const [uploadActor, setUploadActor] = useState('')
  const [uploadReason, setUploadReason] = useState('')
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [uploadMessage, setUploadMessage] = useState('')
  const { data, error, loading } = useQuery(() => fetchSource(id), [id, detailRefresh])
  const preview = data?.source_type === 'master_excel' ? WORKBOOK_PREVIEWS[data.name] : undefined

  useEffect(() => {
    if (!data) return
    setDisplayName(data.display_name ?? data.name)
    setActive(data.is_active ?? true)
  }, [data])

  async function saveManagement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setSaveError('')
    setSaved(false)
    try {
      await updateSource(id, { display_name: displayName, is_active: active, actor_id: actorId, reason })
      setReason('')
      setSaved(true)
      setDetailRefresh((value) => value + 1)
      onSaved()
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : 'No se ha podido guardar la fuente.')
    } finally {
      setSaving(false)
    }
  }

  async function previewUpload() {
    if (!preview || !workbookFile) return
    setUploadBusy(true)
    setUploadError('')
    setUploadMessage('')
    try {
      setWorkbookPreview(await previewMasterWorkbook(preview.view, workbookFile))
    } catch (cause) {
      setUploadError(cause instanceof Error ? cause.message : 'No se ha podido validar el Excel.')
      setWorkbookPreview(null)
    } finally {
      setUploadBusy(false)
    }
  }

  async function confirmUpload() {
    if (!preview || !workbookFile || !workbookPreview) return
    setUploadBusy(true)
    setUploadError('')
    setUploadMessage('')
    try {
      const result = await importMasterWorkbook(preview.view, workbookFile, {
        sha256: workbookPreview.sha256,
        actor_id: uploadActor,
        reason: uploadReason,
      })
      setUploadMessage(result.created
        ? `Lote ${result.status === 'completed' ? 'completado' : 'creado con incidencias'}: ${result.batch_id}`
        : `Este contenido ya se había importado. Lote existente: ${result.batch_id}`)
      setWorkbookFile(null)
      setWorkbookPreview(null)
      setUploadReason('')
      setDetailRefresh((value) => value + 1)
      onSaved()
    } catch (cause) {
      setUploadError(cause instanceof Error ? cause.message : 'No se ha podido importar el Excel.')
    } finally {
      setUploadBusy(false)
    }
  }

  return (
    <section className='panel' aria-label='Detalle de la fuente'>
      <div className='panel__head'>
        <h2>Detalle de la fuente</h2>
        <button type='button' className='button' onClick={onClose}>
          Cerrar
        </button>
      </div>
      <AsyncBoundary
        loading={loading}
        error={error}
        empty={false}
        emptyTitle=''
        emptyDetail=''
      >
        {data && (
          <>
            <form className='panel' onSubmit={(event) => void saveManagement(event)} aria-label='Gestionar fuente'>
              <h3>Gestionar fuente</h3>
              <p>El nombre visible se puede cambiar sin modificar el archivo original ni su historial.</p>
              <label className='field'>
                <span>Nombre visible</span>
                <input required maxLength={200} value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
              </label>
              <label className='field'>
                <span>Responsable del cambio</span>
                <input required maxLength={80} value={actorId} onChange={(event) => setActorId(event.target.value)} />
              </label>
              <label className='field'>
                <span>Motivo</span>
                <input required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} />
              </label>
              <label className='field field--inline'>
                <input type='checkbox' checked={active} onChange={(event) => setActive(event.target.checked)} />
                <span>Mostrar en el listado habitual de fuentes</span>
              </label>
              {saveError && <p role='alert'>{saveError}</p>}
              {saved && <p role='status'>Cambios guardados.</p>}
              <button className='button button--primary' type='submit' disabled={saving}>
                {saving ? 'Guardando…' : 'Guardar cambios'}
              </button>
            </form>
            {(data.management_history?.length ?? 0) > 0 && <section className='panel' aria-label='Historial de gestión de la fuente'>
              <h3>Historial de gestión</h3>
              <ul>{data.management_history.map((revision, index) => <li key={`${revision.created_at}-${index}`}>
                {formatDateTime(revision.created_at)} · {revision.actor_id} · {revision.is_active ? 'Fuente visible' : 'Fuente archivada'}
                <p>Nombre: {revision.previous_display_name ?? data.name} → {revision.display_name}</p>
                <p>{revision.reason}</p>
              </li>)}</ul>
            </section>}
            {preview && <div className={`source-workbook-preview source-workbook-preview--${preview.view}`}>
              <p className='eyebrow'>Vista del libro maestro</p>
              <h3>{preview.title}</h3>
              <p>{preview.description}</p>
              <p>Abra un registro para consultar todas sus hojas y anotar o corregir valores con revisor y motivo. El Excel original se conserva.</p>
              <button type='button' className='button button--primary' onClick={() => openCatalogSource(preview.view)}>
                {preview.action}
              </button>
            </div>}
            {preview && <section className='panel' aria-label='Actualizar libro maestro'>
              <h3>Importar una nueva versión</h3>
              <p>Selecciona un Excel con la misma estructura. La vista previa no modifica los datos; la importación se confirma después.</p>
              <label className='field'>
                <span>Libro Excel</span>
                <input
                  type='file'
                  accept='.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                  onChange={(event) => {
                    setWorkbookFile(event.target.files?.[0] ?? null)
                    setWorkbookPreview(null)
                    setUploadError('')
                    setUploadMessage('')
                  }}
                />
              </label>
              <button type='button' className='button' disabled={!workbookFile || uploadBusy} onClick={() => void previewUpload()}>
                {uploadBusy && !workbookPreview ? 'Validando…' : 'Ver vista previa'}
              </button>
              {workbookPreview && <>
                <p>{workbookPreview.workbook} · {(workbookPreview.size_bytes / (1024 * 1024)).toLocaleString('es-ES', { maximumFractionDigits: 1 })} MiB · {workbookPreview.data_rows.toLocaleString('es-ES')} filas · SHA-256 <code>{shortHash(workbookPreview.sha256)}</code></p>
                <table className='table'>
                  <caption>Contenido detectado</caption>
                  <thead><tr><th>Hoja</th><th>Columnas</th><th>Filas de datos</th></tr></thead>
                  <tbody>{workbookPreview.sheets.map((sheet) => <tr key={sheet.name}>
                    <th scope='row'>{sheet.name}</th><td>{sheet.columns}</td><td>{sheet.data_rows.toLocaleString('es-ES')}</td>
                  </tr>)}</tbody>
                </table>
                {workbookPreview.blocked_reason && <p role='note'>{workbookPreview.blocked_reason}</p>}
                <label className='field'>
                  <span>Responsable de la importación</span>
                  <input required maxLength={80} value={uploadActor} onChange={(event) => setUploadActor(event.target.value)} />
                </label>
                <label className='field'>
                  <span>Motivo</span>
                  <input required maxLength={1000} value={uploadReason} onChange={(event) => setUploadReason(event.target.value)} />
                </label>
                <button type='button' className='button button--primary' disabled={uploadBusy || !workbookPreview.can_import || !uploadActor.trim() || !uploadReason.trim()} onClick={() => void confirmUpload()}>
                  {uploadBusy ? 'Importando…' : 'Confirmar importación'}
                </button>
              </>}
              {uploadError && <p role='alert'>{uploadError}</p>}
              {uploadMessage && <p role='status'>{uploadMessage}</p>}
            </section>}
            <dl className='definition'>
              <div>
                <dt>Nombre</dt>
                <dd>{data.name}</dd>
              </div>
              <div>
                <dt>Tipo</dt>
                <dd>{SOURCE_TYPE_LABELS[data.source_type] ?? data.source_type}</dd>
              </div>
              <div>
                <dt>Versiones documentales</dt>
                <dd>{data.versions}</dd>
              </div>
              <div>
                <dt>Versión declarada</dt>
                <dd>{orDash(data.latest_version)}</dd>
              </div>
              <div>
                <dt>Hash de contenido</dt>
                <dd title={data.latest_content_hash ?? undefined}>
                  <code>{shortHash(data.latest_content_hash)}</code>
                </dd>
              </div>
              <div>
                <dt>Última actualización</dt>
                <dd>{formatDateTime(data.last_updated_at)}</dd>
              </div>
              <div>
                <dt>Registros enlazados</dt>
                <dd>{data.records.toLocaleString('es-ES')}</dd>
              </div>
              <div>
                <dt>Incidencias</dt>
                <dd>{data.diagnostics}</dd>
              </div>
            </dl>

            {data.sheets.length > 0 ? (
              <div className='table-wrap' role='region' aria-label='Hojas del libro; desplazamiento horizontal disponible' tabIndex={0}>
              <table className='table'>
                <caption>Hojas importadas</caption>
                <thead>
                  <tr>
                    <th scope='col'>Hoja</th>
                    <th scope='col'>Contenido</th>
                    <th scope='col'>Filas de datos</th>
                    <th scope='col'>Valores con contenido</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sheets.map((sheet) => (
                    <tr key={sheet.sheet_ordinal}>
                      <th scope='row'>{sheet.sheet_name}</th>
                      <td>{preview?.sheets[sheet.sheet_name] ?? 'Hoja de origen'}{sheet.data_row_count === 0 ? ' · solo cabecera' : ''}</td>
                      <td>{sheet.data_row_count.toLocaleString('es-ES')}</td>
                      <td>{sheet.material_value_count.toLocaleString('es-ES')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            ) : (
              <p className='muted'>
                Esta fuente no registra hojas importadas: no procede de un libro Excel.
              </p>
            )}
          </>
        )}
      </AsyncBoundary>
    </section>
  )
}

export function SourcesScreen() {
  const [selected, setSelected] = useState<string | null>(null)
  const [selectedUpload, setSelectedUpload] = useState<CatalogSourceWorkbook | null>(null)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [showDocuments, setShowDocuments] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const { data, error, loading } = useQuery(() => fetchSources(includeArchived), [includeArchived, refresh])
  const { data: databaseInfo } = useQuery(fetchDatabaseInfo, [])
  const cimaDocuments = data?.items.filter((item) => item.source_type.startsWith('cima')).length ?? 0

  return (
    <div className='screen'>
      <PageHeader eyebrow='Datos' title='Fuentes de datos' description='Gestiona los tres maestros Excel, consulta CIMA y prepara las conexiones externas. Cada fuente indica si tiene datos cargados en este entorno.' />

      <section aria-label='Maestros Excel'>
        <div className='source-section-heading'><div><p className='eyebrow'>Archivos principales</p><h2>Maestros Excel</h2></div><span className='badge'>{databaseInfo?.mode === 'demo' ? 'Entorno DEMO' : 'Entorno REAL'}</span></div>
        <div className='source-card-grid'>
          {Object.entries(WORKBOOK_PREVIEWS).map(([filename, profile]) => {
            const source = data?.items.find((item) => item.source_type === 'master_excel' && item.name === filename)
            return <article className='panel source-master-card' key={filename}>
              <p className='eyebrow'>{profile.view.replace('_', ' ')}</p>
              <h3>{profile.title}</h3>
              <p className='source-filename'>{filename}</p>
              <p>{source ? `${source.records.toLocaleString('es-ES')} registros · ${source.versions} versión(es)` : 'Sin datos cargados en este entorno'}</p>
              <div className='source-actions'>
                {source && <button type='button' className='button button--primary' onClick={() => { setSelected(source.key); setSelectedUpload(null) }}>Gestionar y ver versiones</button>}
                {source && <button type='button' className='button' onClick={() => openCatalogSource(profile.view)}>{profile.action}</button>}
                {!source && databaseInfo?.mode === 'real' && <button type='button' className='button button--primary' onClick={() => { setSelectedUpload(profile.view); setSelected(null) }}>Cargar primer Excel</button>}
              </div>
            </article>
          })}
        </div>
        {databaseInfo?.mode === 'demo' && <p className='muted'>Esta base DEMO contiene datos sintéticos. Los tres maestros originales están en la vista previa REAL.</p>}
        {selectedUpload && <section className='panel' aria-label='Cargar maestro Excel'>
          <div className='panel__head'><h3>Cargar {selectedUpload.replace('_', ' ')}</h3><button type='button' className='button' onClick={() => setSelectedUpload(null)}>Cerrar</button></div>
          <MasterUpload kind={selectedUpload} onImported={() => { setSelectedUpload(null); setRefresh((value) => value + 1) }} />
        </section>}
      </section>

      <section className='source-connector-grid' aria-label='Otras fuentes'>
        <NomenclatorConnection />
        <div className='source-connector-stack'>
          <section className='panel source-connector' aria-label='CIMA'>
            <div className='panel__head'><div><p className='eyebrow'>Agencia Española de Medicamentos</p><h2>CIMA</h2></div><span className='badge'>{cimaDocuments ? 'Con datos' : 'Sin documentos'}</span></div>
            <p>{cimaDocuments.toLocaleString('es-ES')} documentos registrados en esta base. Las novedades y el mantenimiento siguen disponibles.</p>
            <a className='button' href='#/novedades'>Ver novedades CIMA</a>
          </section>
          <section className='panel source-connector' aria-label='BOT PLUS Web'>
            <div className='panel__head'><div><p className='eyebrow'>Consulta externa</p><h2>BOT PLUS Web</h2></div><span className='badge'>Pendiente de integración</span></div>
            <p>Acceso a la cuenta web de consulta. La incorporación automática de datos requiere el servicio de integración y sus permisos; las credenciales se configurarán cuando estén disponibles.</p>
            <a className='button' href='https://botplusweb.farmaceuticos.com/' target='_blank' rel='noopener noreferrer'>Abrir BOT PLUS Web</a>
          </section>
        </div>
      </section>

      <section className='panel' aria-label='Documentos registrados'>
        <div className='panel__head'><div><p className='eyebrow'>Inventario</p><h2>Documentos registrados</h2></div><button type='button' className='button' onClick={() => setShowDocuments((value) => !value)}>{showDocuments ? 'Ocultar documentos' : 'Mostrar documentos'}</button></div>
        <p>Consulta los documentos individuales, incluidos los de CIMA y los conjuntos de demostración.</p>
      {showDocuments && <>

      <label className='field field--inline'>
        <input type='checkbox' checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />
        <span>Mostrar fuentes archivadas</span>
      </label>

      <AsyncBoundary
        loading={loading}
        error={error}
        empty={(data?.items.length ?? 0) === 0}
        emptyTitle='No hay ninguna fuente cargada'
        emptyDetail={
          'No existe ningún documento de origen en la base de datos. Las fuentes aparecen ' +
          'aquí cuando una importación las registra.'
        }
      >
        {data && (
          <div className='table-wrap' role='region' aria-label='Fuentes; desplazamiento horizontal disponible' tabIndex={0}>
          <table className='table'>
            <thead>
              <tr>
                <th scope='col'>Fuente</th>
                <th scope='col'>Tipo</th>
                <th scope='col'>Estado</th>
                <th scope='col'>Versión</th>
                <th scope='col' className='cell--num'>Registros</th>
                <th scope='col' className='cell--num'>Lotes</th>
                <th scope='col' className='cell--num'>Incidencias</th>
                <th scope='col'>Actualizada</th>
                <th scope='col'>
                  <span className='visually-hidden'>Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.key}>
                  <th scope='row'>{item.display_name || item.name}{item.is_active === false && ' · Archivada'}</th>
                  <td>{SOURCE_TYPE_LABELS[item.source_type] ?? item.source_type}</td>
                  <td>
                    <span className={`badge badge--${item.status}`}>
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </td>
                  <td>{orDash(item.latest_version)}</td>
                  <td className='cell--num'>{item.records.toLocaleString('es-ES')}</td>
                  <td className='cell--num'>{item.batches}</td>
                  <td className='cell--num'>{item.diagnostics + item.quarantined_rows}</td>
                  <td>{formatDateTime(item.last_updated_at)}</td>
                  <td>
                    <button
                      type='button'
                      className='button'
                      onClick={() => setSelected(item.key)}
                    >
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </AsyncBoundary>
      </>}
      </section>

      {selected && <SourceDetail id={selected} onClose={() => setSelected(null)} onSaved={() => setRefresh((value) => value + 1)} />}
    </div>
  )
}
