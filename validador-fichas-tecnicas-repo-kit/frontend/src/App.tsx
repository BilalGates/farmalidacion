import { appConfig } from './config'

const boundaries = [
  'Sin datos de pacientes',
  'Sin propuestas clínicas',
  'Sin exportación activa',
]

export function App() {
  return (
    <main className='shell'>
      <header className='hero'>
        <p className='eyebrow'>Entorno técnico · Fase 1</p>
        <h1>Validador de fichas técnicas</h1>
        <p className='lede'>
          Scaffold de inspección de la arquitectura. La revisión farmacéutica todavía no está habilitada.
        </p>
      </header>

      <section className='status-card' aria-labelledby='system-status'>
        <div>
          <p className='section-label'>Estado del sistema</p>
          <h2 id='system-status'>Frontend preparado</h2>
        </div>
        <span className='status-badge'>Local</span>
        <dl>
          <div><dt>API configurada</dt><dd>{appConfig.apiBaseUrl}</dd></div>
          <div><dt>Siguiente capacidad</dt><dd>Persistencia y migraciones</dd></div>
        </dl>
      </section>

      <section aria-labelledby='current-boundaries'>
        <p className='section-label'>Límites activos</p>
        <h2 id='current-boundaries'>Este corte no toma decisiones farmacéuticas</h2>
        <ul className='boundary-list'>
          {boundaries.map((boundary) => <li key={boundary}>{boundary}</li>)}
        </ul>
      </section>
    </main>
  )
}
