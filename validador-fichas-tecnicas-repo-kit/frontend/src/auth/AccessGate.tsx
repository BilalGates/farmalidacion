import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ApiError, fetchAuthConfig, fetchSession, type AuthConfig } from '../api/client'
import { clearRecordCache } from '../api/recordCache'
import { setDraftOwner } from '../domain/drafts'
import { SessionContext, type CorporateSession } from './SessionContext'
import { configureTransport } from './transport'
import type { PublicClientApplication } from '@azure/msal-browser'

export function AccessGate({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [session, setSession] = useState<CorporateSession | null>(null)
  const [busy, setBusy] = useState(true)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const client = useRef<PublicClientApplication | null>(null)
  const epoch = useRef(0)

  useEffect(() => {
    let active = true
    setReady(false)
    client.current = null
    const current = ++epoch.current
    void (async () => {
      try {
        const settings = await fetchAuthConfig()
        if (!active) return
        setConfig(settings)
        if (settings.mode === 'pilot') {
          configureTransport(false, null)
          setDraftOwner(null)
          return
        }
        configureTransport(true, null)
        setDraftOwner('locked')
        if (!settings.configured || !settings.tenant_id || !settings.spa_client_id || !settings.scope) return
        const { PublicClientApplication } = await import('@azure/msal-browser')
        const instance = new PublicClientApplication({
          auth: {
            clientId: settings.spa_client_id,
            authority: `https://login.microsoftonline.com/${settings.tenant_id}`,
            redirectUri: `${window.location.origin}/auth-redirect.html`,
            postLogoutRedirectUri: window.location.origin,
          },
          cache: { cacheLocation: 'sessionStorage' },
        })
        await instance.initialize()
        await instance.handleRedirectPromise()
        if (!active) return
        client.current = instance
        setReady(true)
        // No elegir silenciosamente otra cuenta entre varias identidades.
        const account = instance.getActiveAccount()
        if (!account) return
        configureTransport(true, async () => {
          const result = await instance.acquireTokenSilent({ account, scopes: [settings.scope!] })
          return result.accessToken
        }, expire)
        const identity = await fetchSession()
        if (!active || epoch.current !== current) return
        setDraftOwner(identity.subject_id)
        setSession({ ...identity, logout })
      } catch (cause) {
        if (active) setError(cause instanceof ApiError ? cause.message : 'No se pudo preparar el acceso corporativo.')
      } finally { if (active) setBusy(false) }
    })()
    function expire() {
      epoch.current += 1
      configureTransport(true, null)
      clearRecordCache()
      setDraftOwner('locked')
      setSession(null)
      setError('La sesión ha caducado. Vuelve a iniciar sesión.')
    }
    function logout() {
      expire()
      setError('')
      const instance = client.current
      if (instance) void instance.logoutRedirect({ account: instance.getActiveAccount() }).catch(() => setError('Sesión local cerrada. No se pudo cerrar la sesión de Microsoft.'))
    }
    return () => {
      active = false; epoch.current += 1
      configureTransport(true, null)
      clearRecordCache()
      setDraftOwner('locked')
    }
  }, [attempt])

  async function login() {
    const instance = client.current
    if (!instance || !config?.scope) return
    setBusy(true); setError('')
    const current = ++epoch.current
    try {
      const response = await instance.loginPopup({ scopes: [config.scope], prompt: 'select_account' })
      instance.setActiveAccount(response.account)
      configureTransport(true, async () => {
        const token = await instance.acquireTokenSilent({ account: response.account!, scopes: [config.scope!] })
        return token.accessToken
      }, () => { epoch.current += 1; configureTransport(true, null); clearRecordCache(); setDraftOwner('locked'); setSession(null); setError('La sesión ha caducado. Vuelve a iniciar sesión.') })
      const identity = await fetchSession()
      if (epoch.current !== current) return
      clearRecordCache()
      setDraftOwner(identity.subject_id)
      setSession({ ...identity, logout: () => {
        epoch.current += 1; configureTransport(true, null); clearRecordCache(); setDraftOwner('locked'); setSession(null)
        void instance.logoutRedirect({ account: response.account }).catch(() => setError('Sesión local cerrada. No se pudo cerrar la sesión de Microsoft.'))
      } })
    } catch (cause) {
      configureTransport(true, null)
      setError(cause instanceof ApiError ? cause.message : 'No se pudo iniciar sesión. Inténtalo de nuevo.')
    } finally { setBusy(false) }
  }

  if (config?.mode === 'pilot') return <>{children}</>
  if (session) return <SessionContext.Provider value={session}><div key={session.subject_id}>{children}</div></SessionContext.Provider>
  return <main className='access-screen'><section className='panel access-screen__card'>
    <img src='/brand-mark.svg' alt='' width='42' height='42' />
    <h1>Farmalidación</h1>
    <p>Tu espacio de revisión farmacéutica.</p>
    {busy ? <p role='status'>Preparando acceso…</p> : config?.configured && ready ? <>
      <p className='muted'>Accede con tu cuenta corporativa. Los permisos se comprueban en el servidor.</p>
      <button type='button' className='button button--primary' onClick={() => void login()}>Iniciar sesión con Microsoft</button>
    </> : config?.configured ? <p>No se ha podido preparar la conexión con Microsoft.</p> : config ? <p role='status'>El acceso corporativo está pendiente de configuración por el administrador.</p> : null}
    {error && <p role='alert'>{error}</p>}
    {!busy && (!config || (config.configured && !ready)) && <button type='button' className='button' onClick={() => { setBusy(true); setError(''); setAttempt(value => value + 1) }}>Reintentar conexión</button>}
  </section></main>
}
