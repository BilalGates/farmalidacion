import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { SourceValue } from './SourceValue'

it('mantiene como texto los valores que no son enlaces web', () => {
  render(<SourceValue value='javascript:alert(1)' />)
  expect(screen.queryByRole('link')).not.toBeInTheDocument()
  expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument()
})
