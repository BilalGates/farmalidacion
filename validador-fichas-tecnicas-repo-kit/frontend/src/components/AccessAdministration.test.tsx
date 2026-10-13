import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { AccessAdministration } from './AccessAdministration'

afterEach(() => vi.unstubAllGlobals())

it('muestra por separado la cuenta vinculada y las capacidades corporativas', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    roles: [{ name: 'Admin', capabilities: ['catalog.read', 'team.manage'] }],
    accounts: [{ object_id: 'oid-ana', reviewer_identifier: 'ana', display_name: 'Ana Ruiz', active: true, linked: true }],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })))

  render(<AccessAdministration />)

  expect(await screen.findByText('Ana Ruiz')).toBeVisible()
  expect(screen.getByText('Vínculo verificado')).toBeVisible()
  expect(screen.getByText('Administrar equipo')).toBeVisible()
  expect(screen.getByText('Los permisos de aplicación proceden del rol asignado en Entra; son independientes del rol clínico del revisor.')).toBeVisible()
})
