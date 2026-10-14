const localApiBaseUrl = 'http://127.0.0.1:8000'
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

function resolveApiBaseUrl(): string {
  if (!configuredApiBaseUrl) return localApiBaseUrl

  try {
    const configured = new URL(configuredApiBaseUrl, window.location.origin)
    // A URL relativa o el dominio del propio frontend no identifica al API.
    // En el despliegue personal de Vercel, el API vive en Docker en este PC.
    if (configured.hostname === window.location.hostname) return localApiBaseUrl
    if (configured.protocol !== 'http:' && configured.protocol !== 'https:') {
      return localApiBaseUrl
    }
    return configured.origin
  } catch {
    return localApiBaseUrl
  }
}

const apiBaseUrl = resolveApiBaseUrl()
const apiHostname = new URL(apiBaseUrl).hostname
const isLoopbackApi = apiHostname === 'localhost' || apiHostname === '127.0.0.1' || apiHostname === '[::1]'

type NetworkAddressRequestInit = RequestInit & { targetAddressSpace?: 'loopback' }

export const appConfig = {
  apiBaseUrl,
  apiFetchOptions: (isLoopbackApi ? { targetAddressSpace: 'loopback' } : {}) as NetworkAddressRequestInit,
} as const
