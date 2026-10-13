/** Token sólo en cabecera; cancelar resultados de una sesión que ya terminó. */
export class SessionError extends Error {}

let tokenProvider: (() => Promise<string>) | null = null
let onExpired: (() => void) | null = null
let corporate = false
let generation = 0

export function configureTransport(isCorporate: boolean, provider: (() => Promise<string>) | null, expired: (() => void) | null = null) {
  corporate = isCorporate
  tokenProvider = provider
  onExpired = expired
  generation += 1
}

export async function authenticatedFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const current = generation
  const provider = tokenProvider
  const expired = onExpired
  const isCorporate = corporate
  const headers = new Headers(init.headers)
  if (isCorporate) {
    if (!provider) throw new SessionError('Inicia sesión para acceder.')
    try { headers.set('Authorization', `Bearer ${await provider()}`) }
    catch {
      if (current !== generation) throw new SessionError('La sesión ha terminado.')
      expired?.()
      throw new SessionError('La sesión ha caducado. Vuelve a iniciar sesión.')
    }
  }
  if (current !== generation) throw new SessionError('La sesión ha terminado.')
  const response = await fetch(url, { ...init, headers })
  if (current !== generation) throw new SessionError('La sesión ha terminado.')
  if (isCorporate && response.status === 401) expired?.()
  return response
}
