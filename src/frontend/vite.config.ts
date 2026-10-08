/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Single source of truth for the app version: the repo-root VERSION file.
const appVersion = readFileSync(
  fileURLToPath(new URL('../../VERSION', import.meta.url)),
  'utf-8',
).trim()

const apiTarget = process.env.POKER_API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  server: {
    proxy: {
      '/api': apiTarget,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
