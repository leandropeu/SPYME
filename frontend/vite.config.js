import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8010'
  const backendWsTarget = backendTarget.replace(/^http/i, 'ws')

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5174,
      proxy: {
        '/api': backendTarget,
        '/ws': {
          target: backendWsTarget,
          ws: true,
        },
      },
    },
  }
})
