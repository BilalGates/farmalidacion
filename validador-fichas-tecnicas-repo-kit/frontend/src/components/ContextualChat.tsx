import { FormEvent, useState } from 'react'

import { ApiError, askDocument } from '../api/client'
import type { ContextualChatResult } from '../api/client'

export function ContextualChat({ recordId }: { recordId: string }) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<ContextualChatResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!question.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      setResult(await askDocument(recordId, question.trim()))
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : 'No se pudo consultar el documento.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className='context-chat'>
      <button
        type='button'
        className='button button--ghost'
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        Consulta documental
      </button>
      {open && (
        <div className='context-chat__body'>
          <p className='muted'>Sólo localiza texto de la ficha. No escribe campos ni ofrece recomendaciones.</p>
          <form onSubmit={(event) => void submit(event)}>
            <label className='field'>
              <span className='field__label'>Pregunta sobre el documento</span>
              <input
                value={question}
                maxLength={500}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder='Ej.: enséñame el apartado 6.3'
              />
            </label>
            <button type='submit' className='button' disabled={loading || !question.trim()}>
              {loading ? 'Buscando…' : 'Buscar evidencia'}
            </button>
          </form>
          {error && <p className='field-error' role='alert'>{error}</p>}
          {result && (
            <div aria-live='polite'>
              <p>{result.message}</p>
              {result.citations.map((citation, index) => (
                <figure key={`${citation.document_version_id}-${citation.section}-${index}`}>
                  <blockquote>{citation.literal_text}</blockquote>
                  <figcaption>
                    Apartado {citation.section} · versión {citation.document_version_id}
                  </figcaption>
                </figure>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
