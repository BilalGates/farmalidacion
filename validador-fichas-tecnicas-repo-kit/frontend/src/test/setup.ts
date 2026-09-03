import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// `globals` está desactivado en la configuración de Vitest, de modo que la
// limpieza automática de Testing Library no se registra sola. Sin ella, los
// árboles renderizados se acumulan entre pruebas y las consultas encuentran
// elementos duplicados de la prueba anterior.
afterEach(cleanup)
