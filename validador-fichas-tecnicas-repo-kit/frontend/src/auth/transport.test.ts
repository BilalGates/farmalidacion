import { afterEach, expect, it, vi } from 'vitest'
import { authenticatedFetch, configureTransport } from './transport'

afterEach(() => { configureTransport(false, null); vi.unstubAllGlobals() })

it('envía el token sólo en Authorization y conserva cabeceras de importación', async () => {
  const fetch = vi.fn(async () => new Response('{}'))
  vi.stubGlobal('fetch', fetch)
  configureTransport(true, async () => 'synthetic-token')
  await authenticatedFetch('http://localhost/api', { headers: { 'X-Import-Actor': 'ana' } })
  const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).not.toContain('synthetic-token')
  expect(new Headers(init.headers).get('Authorization')).toBe('Bearer synthetic-token')
  expect(new Headers(init.headers).get('X-Import-Actor')).toBe('ana')
})

it('el modo corporativo sin sesión no consulta datos', async () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  configureTransport(true, null)
  await expect(authenticatedFetch('/records')).rejects.toThrow('Inicia sesión')
  expect(fetch).not.toHaveBeenCalled()
})

it('un token fallido de una cuenta anterior no cierra la nueva sesión', async () => {
  let reject!: (error: Error) => void
  const expiredA = vi.fn()
  const expiredB = vi.fn()
  configureTransport(true, () => new Promise<string>((_, fail) => { reject = fail }), expiredA)
  const result = authenticatedFetch('/records')
  configureTransport(true, async () => 'B', expiredB)
  reject(new Error('old session expired'))
  await expect(result).rejects.toThrow('La sesión ha terminado')
  expect(expiredA).not.toHaveBeenCalled()
  expect(expiredB).not.toHaveBeenCalled()
})

it('descarta una respuesta en vuelo después de cerrar sesión', async () => {
  let finish!: (response: Response) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { finish = resolve })))
  configureTransport(true, async () => 'A')
  const pending = authenticatedFetch('/records')
  await vi.waitFor(() => expect(finish).toBeDefined())
  configureTransport(true, null)
  finish(new Response('{}'))
  await expect(pending).rejects.toThrow('La sesión ha terminado')
})
