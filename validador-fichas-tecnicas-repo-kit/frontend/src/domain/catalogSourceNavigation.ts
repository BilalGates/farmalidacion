import type { CatalogIdentityType, CatalogSourceWorkbook } from '../api/types'
import { navigate } from '../navigation'

export const CATALOG_LIST_STATE_KEY = 'farmalidacion.catalog-list-state'

const identityTypeByWorkbook: Record<CatalogSourceWorkbook, CatalogIdentityType> = {
  especialidades: 'presentation',
  medicamentos: 'dcp',
  principios_activos: 'active_ingredient',
}

export function openCatalogSource(workbook: CatalogSourceWorkbook): void {
  try {
    sessionStorage.setItem(CATALOG_LIST_STATE_KEY, JSON.stringify({
      term: '', query: '', offset: 0, sourceWorkbook: workbook,
      entityType: identityTypeByWorkbook[workbook], sortBy: 'name_asc',
    }))
  } catch { /* El catálogo sigue accesible sin almacenamiento de sesión. */ }
  navigate('/fichas')
}
