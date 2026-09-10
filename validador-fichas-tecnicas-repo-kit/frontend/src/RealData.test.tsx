import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearRecordCache } from './api/recordCache'

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

/**
 * Diagnóstico de la base servida. Es lo que decide el distintivo REAL/DEMO,
 * así que las pruebas lo sustituyen por completo cuando quieren el otro modo.
 */
const REAL_DATABASE = {
  mode: 'real' as const,
  backend: 'sqlite',
  database: 'real',
  records_total: 43381,
  records_real: 43381,
  records_demo: 0,
  import_batches: 4,
  consistent: true,
}

let databaseInfo: unknown = REAL_DATABASE

/**
 * Ficha real servida por `/records/*` tras la convergencia de DEV-503.
 *
 * La revisión —lectura y escritura— pasa por `/records`, que es donde viven las
 * barreras de estados y de identidad del revisor. `/insights` se queda como
 * superficie de consulta y ya no sirve la pantalla de revisión.
 */
const REVIEW_DETAIL = {
  id: 'rec-real',
  entity_type: 'specialty',
  external_identifiers: [
    {
      source_system: 'master_excel',
      source_identifier: '317291008',
      source_version: '2026-06-19',
    },
  ],
  blocks: [
    {
      id: 'block-1',
      block_type: 'specialty_general',
      ordinal: 1,
      values: [
        {
          id: 'value-1',
          field_name: 'ME_DESCRIPCION',
          literal_value: 'Omeprazol 20 mg cápsula',
          observed_type: 'text',
          logical_state: 'valued',
          validation_state: 'pendiente' as const,
          conflict_status: 'single_source',
          has_conflict: false,
          history: [],
          prefill_policy: 'solo_evidencia' as const,
          prefill_presentation: 'casilla_vacia' as const,
          proposed_value: null,
          prefill_options: [],
          prefill_warning:
            'La ficha técnica no declara este dato. Este valor es criterio farmacéutico.',
          provenance: [
            {
              source_fragment_id: 'frag-1',
              document_version_id: 'ver-1',
              locator_type: 'excel_row',
              locator: '{"row":15991,"sheet":"General"}',
              literal_text: 'Omeprazol 20 mg cápsula dura EFG',
              provenance_role: 'master_baseline',
            },
          ],
        },
        {
          id: 'value-2',
          field_name: 'CODIGO_NACIONAL',
          literal_value: '707703',
          observed_type: 'text',
          logical_state: 'valued',
          validation_state: 'pendiente' as const,
          conflict_status: 'single_source',
          has_conflict: false,
          history: [],
          prefill_policy: 'solo_evidencia' as const,
          prefill_presentation: 'casilla_vacia' as const,
          proposed_value: null,
          prefill_options: [],
          prefill_warning:
            'La ficha técnica no declara este dato. Este valor es criterio farmacéutico.',
          provenance: [
            {
              source_fragment_id: 'frag-2',
              document_version_id: 'ver-1',
              locator_type: 'excel_row',
              locator: '{"row":15991,"sheet":"General"}',
              literal_text: null,
              provenance_role: 'master_baseline',
            },
          ],
        },
      ],
    },
  ],
}

/** Devuelve la respuesta simulada según la ruta pedida. */
function route(url: string): unknown {
  if (url.includes('/database-info')) return databaseInfo
  if (url.includes('/insights/dashboard')) return DASHBOARD
  if (url.includes('/insights/sources')) return SOURCES
  if (url.includes('/insights/imports')) return IMPORTS
  if (url.includes('/insights/records/')) return RECORD_DETAIL
  if (url.includes('/insights/records')) {
    return url.includes('origin=demo') ? DEMO_PAGE : RECORD_PAGE
  }
  if (url.includes('/records/reviewers')) return []
  if (/\/records\/[^/]+$/.test(url)) return REVIEW_DETAIL
  throw new Error(`Ruta no simulada: ${url}`)
}

let calls: string[] = []

beforeEach(() => {
  calls = []
  databaseInfo = REAL_DATABASE
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
  // La caché es estado de módulo: sin limpiarla, una prueba serviría
  // la ficha que dejó la anterior.
  clearRecordCache()
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
    window.location.hash = '#/fichas'
    render(<App />)
    expect(await screen.findByText('Omeprazol 20 mg cápsula')).toBeInTheDocument()
    expect(calls.some((url) => url.includes('origin=real'))).toBe(true)
    expect(screen.getByRole('button', { name: /Omeprazol 20 mg cápsula/ })).toBeInTheDocument()
    expect(within(screen.getByRole('complementary', { name: 'Listado de registros' })).getByText('Real')).toBeInTheDocument()
  })

  it('no ofrece datos DEMO dentro del listado de registros', async () => {
    window.location.hash = '#/fichas'
    render(<App />)
    await screen.findByText('Omeprazol 20 mg cápsula')
    expect(screen.queryByRole('button', { name: 'Datos DEMO' })).not.toBeInTheDocument()
    expect(calls.some((url) => url.includes('origin=demo'))).toBe(false)
  })

  it('explica una búsqueda sin resultados en lugar de dejar la tabla vacía', async () => {
    window.location.hash = '#/fichas'
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
  it('abre el detalle REAL desde el listado y conserva la ruta de fichas', async () => {
    window.location.hash = '#/fichas'
    render(<App />)
    await screen.findByText('Omeprazol 20 mg cápsula')

    fireEvent.click(screen.getByRole('button', { name: /Omeprazol 20 mg cápsula/ }))

    await waitFor(() => expect(window.location.hash).toBe('#/fichas/rec-real'))
    expect(await screen.findByText('707703')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Registros/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('sirve la revisión de una ficha real desde /records, no desde /insights', async () => {
    window.location.hash = '#/fichas/rec-real'
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: 'Omeprazol 20 mg cápsula' }),
    ).toBeInTheDocument()
    expect(screen.getByText('707703')).toBeInTheDocument()

    // La convergencia de DEV-503: la pantalla de revisión pide la ficha al
    // árbol que aplica las barreras clínicas, no a la superficie de consulta.
    expect(calls.some((url) => /\/records\/rec-real$/.test(url))).toBe(true)
    expect(calls.some((url) => url.includes('/insights/records/rec-real'))).toBe(false)
  })

  it('muestra la evidencia del campo activo con su procedencia', async () => {
    window.location.hash = '#/fichas/rec-real'
    render(<App />)
    await screen.findByRole('heading', { name: 'Omeprazol 20 mg cápsula' })

    const evidence = screen.getByRole('complementary', { name: 'Evidencia del campo activo' })
    // El primer campo es el activo por defecto y su fuente se muestra literal.
    expect(within(evidence).getByText('Maestro')).toBeInTheDocument()
    expect(within(evidence).getByText('Hoja General, fila 15991')).toBeInTheDocument()
    expect(
      within(evidence).getByText('Omeprazol 20 mg cápsula dura EFG'),
    ).toBeInTheDocument()
  })

  it('no ofrece decidir sin revisor seleccionado', async () => {
    window.location.hash = '#/fichas/rec-real'
    render(<App />)
    await screen.findByRole('heading', { name: 'Omeprazol 20 mg cápsula' })

    fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
    expect(screen.getByRole('button', { name: 'Guardar decisión' })).toBeDisabled()
    expect(screen.getByText(/Seleccione un revisor/)).toBeInTheDocument()
  })
})

describe('fuentes e importaciones', () => {
  it('lista las fuentes con versión, hash y registros', async () => {
    window.location.hash = '#/fuentes'
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Maestro Excel 1 documentos/ }))
    expect(
      await screen.findByText('Especialidades-CargaMaster190626.xlsx'),
    ).toBeInTheDocument()
    const sourceRow = screen.getByRole('row', { name: /Especialidades-CargaMaster190626.xlsx/ })
    expect(within(sourceRow).getByText('29.850')).toBeInTheDocument()
    expect(within(sourceRow).getByText('2026-06-19')).toBeInTheDocument()
  })

  it('lista los lotes ejecutados con sus contadores', async () => {
    window.location.hash = '#/importaciones'
    render(<App />)
    expect(await screen.findByText('specialty_master')).toBeInTheDocument()
    expect(screen.getByText('48.470')).toBeInTheDocument()
    expect(screen.getByText('Completada')).toBeInTheDocument()
  })
})

describe('estado del conjunto de datos', () => {
  it('muestra la fecha de actualización sin distintivo de modo', async () => {
    render(<App />)

    expect(await screen.findByText('Datos actualizados')).toBeVisible()
    expect(document.querySelector('.mode-chip')).toBeNull()
    expect(screen.queryByText(/Datos reales · maestros importados/)).not.toBeInTheDocument()
  })

  it('tampoco muestra un distintivo en modo DEMO', async () => {
    databaseInfo = {
      mode: 'demo',
      backend: 'sqlite',
      database: 'demo',
      records_total: 6,
      records_real: 0,
      records_demo: 6,
      import_batches: 0,
      consistent: true,
    }
    render(<App />)

    await screen.findByText('Datos actualizados')
    expect(document.querySelector('.mode-chip')).toBeNull()
  })

  it('avisa cuando el modo REAL no encuentra ningún registro importado', async () => {
    // Es exactamente la avería que motivó el diagnóstico: base migrada, ingesta
    // sin ejecutar. Callarlo devolvería al usuario a mirar una demo sin saberlo.
    databaseInfo = { ...REAL_DATABASE, records_total: 0, records_real: 0, consistent: false }
    render(<App />)

    const banner = await screen.findByText(/Modo REAL sin datos importados/)
    expect(banner.parentElement?.textContent).toContain('ingest_real_data')
  })

  it('no anuncia ningún modo si el diagnóstico no responde', async () => {
    // Sin diagnóstico no se adivina: afirmar «real» sin saberlo sería el fallo
    // que este distintivo existe para impedir.
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/database-info')) throw new Error('sin respuesta')
        return { ok: true, status: 200, json: async () => route(url) } as Response
      }),
    )
    render(<App />)

    await waitFor(() => expect(screen.queryByText(/Registros reales/)).toBeInTheDocument())
    expect(screen.queryByText(/Datos reales/)).not.toBeInTheDocument()
  })
})

describe('navegación', () => {
  it('marca "Registros" como activo en /#/fichas', async () => {
    window.location.hash = '#/fichas'
    render(<App />)
    await screen.findByText('Omeprazol 20 mg cápsula')
    expect(screen.getByRole('button', { name: /Registros/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('resuelve la antigua ruta /#/registros sobre el listado único', async () => {
    // El segundo listado se fusionó con éste; los enlaces ya repartidos deben
    // seguir llevando a algún sitio, no a «sección desconocida».
    window.location.hash = '#/registros'
    render(<App />)
    await screen.findByText('Omeprazol 20 mg cápsula')
    expect(screen.getByRole('button', { name: /Registros/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('no anuncia en el menú módulos que aún no existen', () => {
    window.location.hash = '#/fichas'
    render(<App />)
    expect(screen.queryByRole('button', { name: /Historial \/ Auditoría/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Configuración/ })).toBeNull()
  })
})

describe('manejo de errores y reintento', () => {
  it('muestra error y botón de reintento cuando falla /insights/records', async () => {
    let callCount = 0
    window.location.hash = '#/fichas'
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/database-info'))
          return { ok: true, status: 200, json: async () => REAL_DATABASE } as Response
        if (url.includes('/records/reviewers'))
          return { ok: true, status: 200, json: async () => [] } as Response
        if (url.includes('/insights/records')) {
          callCount += 1
          if (callCount === 1) {
            return {
              ok: false,
              status: 500,
              json: async () => ({ detail: 'Error interno del servidor.' }),
            } as Response
          }
          return { ok: true, status: 200, json: async () => RECORD_PAGE } as Response
        }
        throw new Error(`Ruta no simulada: ${url}`)
      }),
    )
    render(<App />)

    expect(await screen.findByText('Error interno del servidor.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Omeprazol 20 mg cápsula')).toBeInTheDocument()
    expect(callCount).toBe(2)
  })
})
