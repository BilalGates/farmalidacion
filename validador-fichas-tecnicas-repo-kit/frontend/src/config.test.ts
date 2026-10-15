import { describe, expect, it } from 'vitest'
import { resolveApiBaseUrl } from './config'

describe('resolveApiBaseUrl', () => {
  it('uses the local API by default only for local frontend development', () => {
    expect(resolveApiBaseUrl(undefined, 'http://localhost:5173', 'localhost'))
      .toBe('http://127.0.0.1:8000')
    expect(resolveApiBaseUrl(undefined, 'https://farmalidacion-beta.vercel.app', 'farmalidacion-beta.vercel.app'))
      .toBeNull()
  })

  it('rejects the frontend itself as the API', () => {
    expect(resolveApiBaseUrl(
      'https://farmalidacion-beta.vercel.app',
      'https://farmalidacion-beta.vercel.app',
      'farmalidacion-beta.vercel.app',
    )).toBeNull()
  })

  it('accepts an external HTTPS API for a published frontend', () => {
    expect(resolveApiBaseUrl(
      'https://farmalidacion-api.example.com/path',
      'https://farmalidacion-beta.vercel.app',
      'farmalidacion-beta.vercel.app',
    )).toBe('https://farmalidacion-api.example.com')
  })

  it('accepts the same-origin API path for a hosted frontend', () => {
    expect(resolveApiBaseUrl(
      '/api',
      'https://farmalidacion.example.com',
      'farmalidacion.example.com',
    )).toBe('/api')
  })

  it('rejects loopback and insecure HTTP APIs from a public HTTPS page', () => {
    expect(resolveApiBaseUrl(
      'http://127.0.0.1:8000',
      'https://farmalidacion-beta.vercel.app',
      'farmalidacion-beta.vercel.app',
    )).toBeNull()
    expect(resolveApiBaseUrl(
      'http://api.example.com',
      'https://farmalidacion-beta.vercel.app',
      'farmalidacion-beta.vercel.app',
    )).toBeNull()
  })

  it('allows a local development API with a separate port', () => {
    expect(resolveApiBaseUrl(
      'http://localhost:8000',
      'http://localhost:5173',
      'localhost',
    )).toBe('http://localhost:8000')
  })
})
