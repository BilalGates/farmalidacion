import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: { input: {
      app: fileURLToPath(new URL('./index.html', import.meta.url)),
      auth: fileURLToPath(new URL('./auth-redirect.html', import.meta.url)),
    } },
  },
  test: { environment: 'happy-dom', setupFiles: './src/test/setup.ts' },
})
