import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { FilterWorkspace } from './FilterWorkspace'

it('conserva el foco al plegar y desplegar filtros', () => {
  localStorage.removeItem('test.filters.focus')
  render(<FilterWorkspace title='Filtros' storageKey='test.filters.focus' filters={<input aria-label='Filtro' />}><p>Resultados</p></FilterWorkspace>)
  const close = screen.getByRole('button', { name: 'Ocultar filtros' })
  close.focus()
  fireEvent.click(close)
  const reopen = screen.getByRole('button', { name: 'Mostrar filtros' })
  expect(reopen).toHaveFocus()
  fireEvent.click(reopen)
  expect(screen.getByRole('button', { name: 'Ocultar filtros' })).toHaveFocus()
  localStorage.removeItem('test.filters.focus')
})
