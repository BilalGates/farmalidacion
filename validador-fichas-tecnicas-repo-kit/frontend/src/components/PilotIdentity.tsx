import { useState } from 'react'
import type { Reviewer } from '../api/types'

/** Sólo identificación declarada: nunca se presenta como autenticación. */
export function PilotIdentity({ reviewers, reviewer, onChange }: { reviewers: Reviewer[]; reviewer: Reviewer | null; onChange: (id: string) => void }) {
  const [candidate, setCandidate] = useState('')
  return <section className='panel identity-preferences' aria-labelledby='identity-title'>
    <h2 id='identity-title'>Identidad y acceso</h2>
    <p className='muted'>El acceso corporativo con Microsoft Entra ID está pendiente de configuración.</p>
    <p className='mode-banner mode-banner--warning'>Este entorno usa identificación declarada del piloto. No verifica tu identidad ni restringe el acceso mediante una sesión autenticada.</p>
    {reviewer ? <div className='identity-preferences__current'>
      <span><strong>{reviewer.display_name}</strong><small>{reviewer.role_label} · Identidad declarada</small></span>
      <button type='button' className='button' onClick={() => { onChange(''); setCandidate('') }}>Finalizar identificación</button>
    </div> : <form className='identity-preferences__form' onSubmit={event => { event.preventDefault(); if (reviewers.some(item => item.identifier === candidate)) onChange(candidate) }}>
      <label className='field'><span className='field__label'>Revisor del piloto</span><select value={candidate} onChange={event => setCandidate(event.target.value)} required><option value=''>Elige tu identidad</option>{reviewers.map(item => <option key={item.identifier} value={item.identifier}>{item.display_name} · {item.role_label}</option>)}</select></label>
      <button type='submit' className='button button--primary' disabled={!candidate}>Identificarse en el piloto</button>
    </form>}
  </section>
}
