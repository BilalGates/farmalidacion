const localApiBaseUrl = 'http://127.0.0.1:8000'
const localHostnames = new Set(['localhost', '127.0.0.1', '[::1]'])

export function resolveApiBaseUrl(
  configuredValue: string | undefined,
  locationOrigin: string,
  locationHostname: string,
): string | null {
  const isLocalFrontend = localHostnames.has(locationHostname)
  const configuredApiBaseUrl = configuredValue?.trim()
  if (!configuredApiBaseUrl) return isLocalFrontend ? localApiBaseUrl : null

  try {
    const configured = new URL(configuredApiBaseUrl)
    if (configured.protocol !== 'http:' && configured.protocol !== 'https:') return null
    if (configured.origin === locationOrigin) return null
    if (localHostnames.has(configured.hostname) && !isLocalFrontend) return null
    if (
      locationOrigin.startsWith('https://') &&
      configured.protocol !== 'https:' &&
      !isLocalFrontend
    ) {
      return null
    }
    return configured.origin
  } catch {
    return null
  }
}

export const appConfig = {
  apiBaseUrl: resolveApiBaseUrl(
    import.meta.env.VITE_API_BASE_URL,
    window.location.origin,
    window.location.hostname,
  ),
} as const
