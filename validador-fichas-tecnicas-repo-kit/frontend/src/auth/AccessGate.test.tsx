import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AccessGate } from './AccessGate'
import { useCorporateSession } from './SessionContext'
import { configureTransport } from './transport'
import { readDraft, saveDraft, setDraftOwner } from '../domain/drafts'

const msal = vi.hoisted(() => ({
  initialize: vi.fn(async () => undefined), handleRedirectPromise: vi.fn(async () => null),
  getActiveAccount: vi.fn(() => null), setActiveAccount: vi.fn(),
  loginPopup: vi.fn(async () => ({ account: { homeAccountId: 'synthetic' } })),
  acquireTokenSilent: vi.fn(async () => ({ accessToken: 'synthetic-token' })),
  logoutRedirect: vi.fn(async () => undefined),
}))
vi.mock('@azure/msal-browser', () => ({ PublicClientApplication: class { constructor() { return msal } } }))

function Workspace() {
  const session = useCorporateSession()
  return <div>Contenido protegido{session && <><p>{session.reviewer.display_name}</p><button onClick={session.logout}>Cerrar sesión</button></>}</div>
}
const settings = { mode: 'entra', configured: true, tenant_id: 'tenant', spa_client_id: 'spa', scope: 'api://test/access_as_user' }
const identity = { subject_id: 'entra:tenant:ana', capabilities: ['catalog.read'], reviewer: { identifier: 'ana', display_name: 'Ana', assurance: 'verificada_entra', role: 'farmaceutico', role_label: 'Farmacéutico', may_sign_pharmacist_states: true } }
function respond(config = settings, status = 200) {
  const fetch = vi.fn(async (url: RequestInfo | URL) => String(url).endsWith('/auth/config')
    ? new Response(JSON.stringify(config), { status: 200 })
    : new Response(JSON.stringify(status === 200 ? identity : { detail: 'Cuenta sin permisos.' }), { status }))
  vi.stubGlobal('fetch', fetch)
  return fetch
}
afterEach(() => { configureTransport(false, null); setDraftOwner(null); localStorage.clear(); vi.unstubAllGlobals(); vi.clearAllMocks() })

it('mantiene el piloto explícito cuando el servidor declara ese modo', async () => {
  respond({ ...settings, mode: 'pilot', configured: false })
  render(<AccessGate><Workspace /></AccessGate>)
  expect(await screen.findByText('Contenido protegido')).toBeInTheDocument()
})

it('no monta el programa mientras falta sesión o configuración corporativa', async () => {
  respond({ ...settings, configured: false })
  render(<AccessGate><Workspace /></AccessGate>)
  expect(await screen.findByText(/pendiente de configuración/)).toBeInTheDocument()
  expect(screen.queryByText('Contenido protegido')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Iniciar sesión/ })).not.toBeInTheDocument()
})

it('abre el programa sólo tras la autorización del servidor y lo retira al salir', async () => {
  const fetch = respond()
  render(<AccessGate><Workspace /></AccessGate>)
  fireEvent.click(await screen.findByRole('button', { name: 'Iniciar sesión con Microsoft' }))
  expect(await screen.findByText('Ana')).toBeInTheDocument()
  const call = fetch.mock.calls.find(([url]) => String(url).endsWith('/auth/me'))
  expect(call).toBeDefined()
  expect(msal.acquireTokenSilent).toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
  await waitFor(() => expect(screen.queryByText('Contenido protegido')).not.toBeInTheDocument())
  expect(msal.logoutRedirect).toHaveBeenCalled()
})

it('una cuenta Microsoft válida sin permiso no accede al programa', async () => {
  respond(settings, 403)
  render(<AccessGate><Workspace /></AccessGate>)
  fireEvent.click(await screen.findByRole('button', { name: 'Iniciar sesión con Microsoft' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Cuenta sin permisos.')
  expect(screen.queryByText('Contenido protegido')).not.toBeInTheDocument()
})

it('permite reintentar si falla la preparación de Microsoft', async () => {
  respond()
  msal.initialize.mockRejectedValueOnce(new Error('offline'))
  render(<AccessGate><Workspace /></AccessGate>)
  fireEvent.click(await screen.findByRole('button', { name: 'Reintentar conexión' }))
  expect(await screen.findByRole('button', { name: 'Iniciar sesión con Microsoft' })).toBeEnabled()
  expect(screen.queryByText('Contenido protegido')).not.toBeInTheDocument()
})

it('conserva los borradores por propietario sin heredarlos del piloto o de otra cuenta', () => {
  setDraftOwner(null)
  saveDraft('record', 'field', { state: '', finalValue: 'Piloto', comment: '' })
  setDraftOwner('entra:tenant:ana')
  expect(readDraft('record', 'field')).toBeNull()
  saveDraft('record', 'field', { state: '', finalValue: 'Ana', comment: '' })
  setDraftOwner('entra:tenant:luis')
  expect(readDraft('record', 'field')).toBeNull()
  setDraftOwner('entra:tenant:ana')
  expect(readDraft('record', 'field')?.finalValue).toBe('Ana')
  setDraftOwner(null)
  expect(readDraft('record', 'field')?.finalValue).toBe('Piloto')
})
