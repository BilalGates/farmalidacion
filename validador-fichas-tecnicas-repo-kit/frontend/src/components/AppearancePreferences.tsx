import type { ReadingDensity, ThemeChoice } from '../domain/appearance'

export interface AppearancePreferencesProps {
  theme: ThemeChoice
  density: ReadingDensity
  onThemeChange: (value: ThemeChoice) => void
  onDensityChange: (value: ReadingDensity) => void
}

export function AppearancePreferences({ theme, density, onThemeChange, onDensityChange }: AppearancePreferencesProps) {
  return <section className='panel appearance-preferences' aria-labelledby='appearance-title'>
    <div><h2 id='appearance-title'>Lectura y apariencia</h2><p className='muted'>Adapta el espacio a tu forma de trabajar. Estas preferencias se guardan en este navegador.</p></div>
    <div className='appearance-preferences__controls'>
      <label className='field'><span className='field__label'>Densidad de lectura</span><select aria-label='Densidad de lectura' value={density} onChange={event => onDensityChange(event.target.value as ReadingDensity)}><option value='comfortable'>Cómoda</option><option value='compact'>Compacta</option></select><small className='field__hint'>Compacta reduce los espacios y mantiene el tamaño del texto.</small></label>
      <label className='field'><span className='field__label'>Tema visual</span><select aria-label='Tema visual' value={theme} onChange={event => onThemeChange(event.target.value as ThemeChoice)}><option value='system'>Según el sistema</option><option value='light'>Claro</option><option value='dark'>Oscuro</option></select><small className='field__hint'>El tema y la densidad se eligen de forma independiente.</small></label>
    </div>
  </section>
}
