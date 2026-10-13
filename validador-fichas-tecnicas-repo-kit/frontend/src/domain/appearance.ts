export type ThemeChoice = 'system' | 'light' | 'dark'
export type ReadingDensity = 'comfortable' | 'compact'

/** Preferencias locales: nunca forman parte de una firma o del dato clínico. */
export function readAppearance() {
  try {
    const theme = localStorage.getItem('farmalidacion.theme')
    const density = localStorage.getItem('farmalidacion.density')
    return {
      theme: (theme === 'light' || theme === 'dark' ? theme : 'system') as ThemeChoice,
      density: (density === 'compact' ? 'compact' : 'comfortable') as ReadingDensity,
    }
  } catch {
    return { theme: 'system' as ThemeChoice, density: 'comfortable' as ReadingDensity }
  }
}

export function saveAppearance(key: 'theme' | 'density', value: ThemeChoice | ReadingDensity) {
  try { localStorage.setItem(`farmalidacion.${key}`, value) } catch { /* La sesión sigue siendo utilizable sin almacenamiento. */ }
}
