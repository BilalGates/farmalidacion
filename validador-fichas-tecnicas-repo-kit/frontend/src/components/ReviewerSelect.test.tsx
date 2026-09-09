import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { ReviewerSelect } from './ReviewerSelect'

const reviewers = [{ identifier: 'mt', display_name: 'M. Torres', assurance: 'declarada' }]

it('abre un menú integrado y comunica la selección', () => {
  const onChange = vi.fn()
  render(<ReviewerSelect reviewers={reviewers} value='' onChange={onChange} />)

  const trigger = screen.getByRole('combobox', { name: 'Revisor que firma las decisiones' })
  fireEvent.click(trigger)
  expect(screen.getByRole('listbox', { name: 'Revisores disponibles' })).toBeVisible()
  fireEvent.click(screen.getByRole('option', { name: /M\. Torres/ }))

  expect(onChange).toHaveBeenCalledWith('mt')
  expect(screen.queryByRole('listbox')).toBeNull()
})

it('cierra el menú con Escape sin cambiar el revisor', () => {
  const onChange = vi.fn()
  render(<ReviewerSelect reviewers={reviewers} value='mt' onChange={onChange} />)
  const trigger = screen.getByRole('combobox', { name: 'Revisor que firma las decisiones' })
  fireEvent.click(trigger)
  fireEvent.keyDown(trigger, { key: 'Escape' })
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(onChange).not.toHaveBeenCalled()
})
