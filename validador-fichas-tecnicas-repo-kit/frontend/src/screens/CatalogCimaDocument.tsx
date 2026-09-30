import { useEffect, useState } from 'react'

import { fetchCatalogCimaDocuments, fetchRecord } from '../api/client'
import type { CatalogCimaDocument, TargetRecord } from '../api/types'
import { formatDateTime } from '../domain/format'
import { CatalogCimaComparisonPanel } from './CatalogCimaComparisonPanel'

interface Props {
  readonly identityId: string
  readonly recordId?: string | null
  readonly reviewerId?: string
}

export function CatalogCimaDocumentReader({ identityId, recordId, reviewerId = '' }: Props) {
  const [documents, setDocuments] = useState<CatalogCimaDocument[]>([])
  const [record, setRecord] = useState<TargetRecord | null>(null)
  const [recordError, setRecordError] = useState('')
  const [selectedFieldId, setSelectedFieldId] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    setLoading(true)
    setError('')
    setDocuments([])
    setQuery('')
    fetchCatalogCimaDocuments(identityId)
      .then((result) => { if (current) setDocuments(result) })
      .catch((caught: unknown) => {
        if (current) setError(caught instanceof Error ? caught.message : 'No se pudo cargar la ficha técnica.')
      })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [identityId])

  useEffect(() => {
    setRecord(null)
    setRecordError('')
    setSelectedFieldId('')
    if (!recordId) return
    let current = true
    fetchRecord(recordId)
      .then((result) => { if (current) setRecord(result) })
      .catch(() => { if (current) setRecordError('No se pudieron cargar los campos del maestro para la búsqueda literal.') })
    return () => { current = false }
  }, [recordId])

  const term = query.trim().toLocaleLowerCase('es')
  const fields = record?.blocks.flatMap((block) => block.values.map((field) => ({
    id: field.id,
    label: `${block.block_type} · ocurrencia ${block.ordinal} · ${field.field_name}${field.source_column_index == null ? '' : ` · columna ${field.source_column_index}`}`,
    value: field.maintained_value === undefined ? field.literal_value : field.maintained_value,
  }))) ?? []
  const selectedField = fields.find((field) => field.id === selectedFieldId)
  return <section className='panel catalog-cima' aria-labelledby='catalog-cima-title'>
    <div className='panel__head'><div><p className='eyebrow'>Documento regulatorio</p><h2 id='catalog-cima-title'>Ficha técnica CIMA</h2></div></div>
    {loading ? <p role='status'>Cargando ficha técnica…</p> : error ? <p role='alert'>{error}</p> : documents.length === 0 ?
      <p>No hay una ficha técnica CIMA vinculada de forma verificada a este registro.</p> : <>
        <label className='field'><span className='field__label'>Buscar en los apartados</span>
          <input type='search' value={query} onChange={(event) => { setQuery(event.target.value); setSelectedFieldId('') }} />
        </label>
        {recordError && <p role='alert'>{recordError}</p>}
        {fields.length > 0 && <div className='catalog-cima__field-search'>
          <label className='field'><span className='field__label'>Localizar un valor de trabajo en la ficha</span>
            <select value={selectedFieldId} onChange={(event) => { setSelectedFieldId(event.target.value); setQuery('') }}>
              <option value=''>Seleccione un campo</option>
              {fields.map((field) => <option key={field.id} value={field.id}>{field.label}</option>)}
            </select>
          </label>
          <p className='muted'>La búsqueda es literal y distingue mayúsculas y espacios. Una aparición no confirma equivalencia clínica; una ausencia no demuestra diferencia.</p>
          {selectedField && (selectedField.value === null || selectedField.value === '' ?
            <p>Este campo no tiene un valor de trabajo que se pueda buscar.</p> :
            <div>
              <p>Valor buscado: <code>{selectedField.value}</code></p>
              {documents.map((document) => {
                const hits = document.sections.map((section, index) => ({ section, index }))
                  .filter(({ section }) => section.literal_text.includes(selectedField.value!))
                return <div key={document.document_version_id}>
                  <strong>Versión {document.source_version || document.document_version_id}</strong>
                  {hits.length === 0 ? <p>Sin aparición literal en esta versión.</p> :
                    <ul>{hits.map(({ section, index }) => <li key={index}>
                      <a href={`#cima-${document.document_version_id}-${index}`}>Apartado {section.locator}</a>
                    </li>)}</ul>}
                </div>
              })}
            </div>)}
        </div>}
        {documents.map((document) => {
          const sections = document.sections.map((section, index) => ({ section, index }))
            .filter(({ section }) => !term || section.locator.toLocaleLowerCase('es').includes(term) ||
              section.literal_text.toLocaleLowerCase('es').includes(term))
          return <div key={document.document_version_id} className='catalog-cima__document'>
            <h3>Registro CIMA {document.document_name}</h3>
            <p className='muted'>Versión {document.source_version || document.document_version_id} · capturada {formatDateTime(document.acquired_at)}</p>
            <p className='muted'>SHA-256: <code>{document.content_hash}</code></p>
            {document.sections.length === 0 ? <p>Esta versión no contiene apartados de texto legibles.</p> :
              sections.length === 0 ? <p>No hay apartados que coincidan con la búsqueda.</p> :
              <div className='catalog-cima__sections'>
                <nav aria-label={`Apartados de ${document.document_name}`}><ul>{sections.map(({ section, index }) =>
                  <li key={`${section.locator}-${index}`}><a href={`#cima-${document.document_version_id}-${index}`}>Apartado {section.locator}</a></li>)}</ul></nav>
                {sections.map(({ section, index }) => <section key={`${section.locator}-${index}`} id={`cima-${document.document_version_id}-${index}`}>
                  <h4>Apartado {section.locator}</h4><pre>{section.literal_text}</pre>
                </section>)}
              </div>}
          </div>
        })}
      </>}
    {!loading && !error && record && <CatalogCimaComparisonPanel
      identityId={identityId}
      reviewerId={reviewerId}
      documents={documents}
      record={record}
      onRefreshRecord={async () => {
        if (recordId) setRecord(await fetchRecord(recordId))
      }}
    />}
  </section>
}
