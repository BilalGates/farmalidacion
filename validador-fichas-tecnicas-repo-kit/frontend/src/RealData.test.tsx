import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'

/**
 * Pruebas de la vertical de datos reales.
 *
 * Se simula `fetch` para ejercitar el cliente HTTP real, igual que la suite de
 * la vertical de revisión. Lo que más importa aquí es la separación REAL/DEMO:
 * si el listado pidiera el conjunto equivocado, o mostrase el origen incorrecto,
 * un revisor podría tomar un dato de demostración por uno importado.
 */

const DASHBOARD = {
  metrics: [
    { key: 'real_records', label: 'Registros reales', value: 43381 },
    { key: 'batches', label: 'Importaciones', value: 4 },
  ],
  pipeline: [
    {
      key: 'maestros',
      label: 'Maestros Excel',
      status: 'disponible',
      detail: '43381 registros importados desde los maestros.',
    },
    {
      key: 'cima',
      label: 'CIMA',
      status: 'pendiente',
      detail: 'No hay documentos CIMA asociados a registros.',
    },
  ],
  last_import_at: '2026-09-04T07:41:56',
  empty: false,
}

const RECORD_PAGE = {
  items: [
    {
      id: 'rec-real',
      entity_type: 'specialty',
      origin: 'real' as const,
      display_name: 'Omeprazol 20 mg cápsula',
      identifier: '317291008',
      source_system: 'master_excel',
      block_count: 1,
      field_count: 57,
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
}

const DEMO_PAGE = {
  items: [
    {
      id: 'rec-demo',
      entity_type: 'medication',
      origin: 'demo' as const,
      display_name: 'DEMO Omeprazol',
      identifier: 'DEMO-0001',
      source_system: 'demo_showcase',
      block_count: 1,
      field_count: 3,
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
}

const RECORD_DETAIL = {
  id: 'rec-real',
  entity_type: 'specialty',
  origin: 'real' as const,
  display_name: 'Omeprazol 20 mg cápsula',
  identifier: '317291008',
  blocks: [
    {
      id: 'block-1',
      block_type: 'specialty_general',
      ordinal: 1,
      values: [
        {
          id: 'value-1',
          field_name: 'CODIGO_NACIONAL',
          literal_value: '707703',
          observed_type: 'text',
          logical_state: 'valued',
          provenance: [
            {
              source_system: 'master_excel',
              document_name: 'Especialidades-CargaMaster190626.xlsx',
              source_locator: 'Especialidades-CargaMaster190626.xlsx',
              source_version: '2026-06-19',
              content_hash: 'a'.repeat(64),
              locator: '{"row":15991,"sheet":"General"}',
              locator_type: 'excel_row',
              provenance_role: 'master_baseline',
              import_batch_id: 'batch-especialidades',
            },
          ],
        },
      ],
    },
  ],
  sources: [
    {
      key: 'maestro',
      label: 'Maestro',
      status: 'disponible',
      detail: 'Registro importado desde los maestros Excel.',
    },
    {
      key: 'cima',
      label: 'CIMA',
      status: 'pendiente',
      detail: 'Vinculación con CIMA pendiente: el modelo no almacena todavía una correspondencia verificada.',
    },
  ],
}

const SOURCES = {
  items: [
    {
      key: 'doc-1',
      name: 'Especialidades-CargaMaster190626.xlsx',
      source_type: 'master_excel',
      status: 'disponible',
      versions: 1,
      latest_version: '2026-06-19',
      latest_content_hash: 'a'.repeat(64),
      last_updated_at: '2026-09-04T07:41:56',
      batches: 1,
      records: 29850,
      diagnostics: 0,
      quarantined_rows: 275,
    },
  ],
  total: 1,
}

const IMPORTS = {
  items: [
    {
      id: 'batch-especialidades',
      source_system: 'master_excel',
      source_locator: 'Especialidades-CargaMaster190626.xlsx',
      source_version: null,
      content_hash: 'a'.repeat(64),
      importer_name: 'specialty_master',
      importer_version: '1.0.0',
      status: 'completed',
      created_at: '2026-09-04T07:41:56',
      completed_at: '2026-09-04T07:45:00',
      processed_rows: 48470,
      retained_records: 29850,
      quarantined_rows: 275,
      diagnostics: 0,
      errors: 0,
    },
  ],
  total: 1,
}

/** Devuelve la respuesta simulada según la ruta pedida. */
function route(url: string): unknown {
  if (url.includes('/insights/dashboard')) return DASHBOARD
  if (url.includes('/insights/sources')) return SOURCES
  if (url.includes('/insights/imports')) return IMPORTS
  if (url.includes('/insights/records/')) return RECORD_DETAIL
  if (url.includes('/insights/records')) {
    return url.includes('origin=demo') ? DEMO_PAGE : RECORD_PAGE
  }
  if (url.includes('/records/reviewers')) return []
  throw new Error(`Ruta no simulada: ${url}`)
}

let calls: string[] = []

beforeEach(() => {
  calls = []
  window.location.hash = ''
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      calls.push(url)
      return {
        ok: true,
        status: 200,
        json: async () => route(url),
      } as Response
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('panel de inicio', () => {
  it('muestra cifras que provienen del backend', async () => {
    render(<App />)
    expect(await screen.findByText('43.381')).toBeInTheDocument()
    expect(screen.getByText('Registros reales')).toBeInTheDocument()
    // El estado de cada etapa llega calculado, no escrito en la interfaz.
    const cima = screen.getByRole('row', { name: /CIMA/ })
    expect(within(cima).getByText('Pendiente')).toBeInTheDocument()
  })

  it('explica el sistema vacío en lugar de mostrar una pantalla en blanco', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        return {
          ok: true,
          status: 200,
          json: async () =>
            url.includes('/insights/dashboard')
              ? { metrics: [], pipeline: [], last_import_at: null, empty: true }
              : [],
        } as Response
      }),
    )
    render(<App />)
    expect(await screen.findByText(/Todavía no hay datos cargados/)).toBeInTheDocument()
    expect(screen.getByText(/ingest_master_files/)).toBeInTheDocument()
  })

  it('muestra el error del backend sin reescribirlo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'La base de datos no responde.' }),
      })) as unknown as typeof fetch,
    )
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('La base de datos no responde.')
  })
})

describe('separación entre datos reales y DEMO', () => {
  it('consulta el origen real por defecto y marca cada fila', async () => {
    window.location.hash = '#/registros'
    render(<App />)
    expect(await screen.findByText('Omeprazol 20 mg cápsula')).toBeInTheDocument()
    expect(calls.some((url) => url.includes('origin=real'))).toBe(true)
    const row = screen.getByRole('row', { name: /Omeprazol 20 mg cápsula/ })
    expect(within(row).getByText('Real')).toBeInTheDocument()
  })

  it('cambia al conjunto DEMO sólo cuando se pide explícitamente', async () => {
    window.location.hash = '#/registros'
    render(<App />)
    await screen.findByText('Omeprazol 20 mg cápsula')

    fireEvent.click(screen.getByRole('button', { name: 'Datos DEMO' }))

    expect(await screen.findByText('DEMO Omeprazol')).toBeInTheDocument()
    expect(calls.some((url) => url.includes('origin=demo'))).toBe(true)
    // El conjunto real desaparece: nunca se muestran mezclados.
    expect(screen.queryByText('Omeprazol 20 mg cápsula')).not.toBeInTheDocument()
    expect(screen.getByText(/no deben usarse como evidencia clínica/)).toBeInTheDocument()
  })

  it('explica una búsqueda sin resultados en lugar de dejar la tabla vacía', async () => {
    window.location.hash = '#/registros'
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const empty = url.includes('q=')
        return {
          ok: true,
          status: 200,
          json: async () =>
            url.includes('/insights/records')
              ? empty
                ? { items: [], total: 0, limit: 50, offset: 0 }
                : RECORD_PAGE
              : [],
        } as Response
      }),
    )
    render(<App />)
    await screen.findByText('Omeprazol 20 mg cápsula')

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'inexistente' } })
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

    expect(await screen.findByText(/La búsqueda no devuelve resultados/)).toBeInTheDocument()
    expect(screen.getByText(/«inexistente»/)).toBeInTheDocument()
  })
})

describe('ficha de un registro real', () => {
  it('muestra el valor y su procedencia bajo demanda', async () => {
    window.location.hash = '#/registros/rec-real'
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Omeprazol 20 mg cápsula' })).toBeInTheDocument()
    expect(screen.getByText('707703')).toBeInTheDocument()

    // La procedencia existe pero está plegada: se pide para verla.
    fireEvent.click(screen.getByText('Ver procedencia'))
    await waitFor(() => {
      expect(screen.getByText('Hoja General, fila 15991')).toBeInTheDocument()
    })
    expect(screen.getByText('Maestro Excel')).toBeInTheDocument()
    expect(screen.getByText('2026-06-19')).toBeInTheDocument()
  })

  it('declara la vinculación con CIMA como pendiente, sin inventarla', async () => {
    window.location.hash = '#/registros/rec-real'
    render(<App />)
    await screen.findByRole('heading', { name: 'Omeprazol 20 mg cápsula' })

    const row = screen.getByRole('row', { name: /CIMA/ })
    expect(within(row).getByText('Pendiente')).toBeInTheDocument()
    expect(within(row).getByText(/Vinculación con CIMA pendiente/)).toBeInTheDocument()
  })
})

describe('fuentes e importaciones', () => {
  it('lista las fuentes con versión, hash y registros', async () => {
    window.location.hash = '#/fuentes'
    render(<App />)
    expect(
      await screen.findByText('Especialidades-CargaMaster190626.xlsx'),
    ).toBeInTheDocument()
    expect(screen.getByText('29.850')).toBeInTheDocument()
    expect(screen.getByText('2026-06-19')).toBeInTheDocument()
  })

  it('lista los lotes ejecutados con sus contadores', async () => {
    window.location.hash = '#/importaciones'
    render(<App />)
    expect(await screen.findByText('specialty_master')).toBeInTheDocument()
    expect(screen.getByText('48.470')).toBeInTheDocument()
    expect(screen.getByText('Completada')).toBeInTheDocument()
  })
})
