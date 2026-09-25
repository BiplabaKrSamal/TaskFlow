import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The browser only ever talks to its own origin. In dev Vite forwards /api (including the
// websocket) to the backend, in Docker nginx does the same, so there is no CORS to configure
// and the refresh cookie stays first-party.
const backend = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: backend, ws: true } } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
