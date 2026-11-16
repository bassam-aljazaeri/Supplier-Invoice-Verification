import react from '@vitejs/plugin-react'
import { createLogger, defineConfig } from 'vite'
import { setDefaultResultOrder } from 'node:dns'
import { privateProxyLogger } from './src/privateProxyLogger.ts'

setDefaultResultOrder('verbatim')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  customLogger: privateProxyLogger(createLogger()),
  // Verification can opt out of ALL environment-file loading, including .env.local.
  envDir: process.env.SIV_NO_ENV_FILES === '1' ? false : undefined,
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
