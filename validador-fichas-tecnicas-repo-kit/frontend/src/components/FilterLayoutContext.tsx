import { createContext, useContext } from 'react'

/** Coordina el espacio de filtros con la navegación, sin cambiar su preferencia. */
export const FilterLayoutContext = createContext<(id: string, open: boolean) => void>(() => {})
export const useFilterLayout = () => useContext(FilterLayoutContext)
