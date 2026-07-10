import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:5000'
  const repoRoot = path.resolve(__dirname, '..')

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@shared': path.join(repoRoot, 'shared'),
      },
    },
    server: {
      fs: {
        allow: [repoRoot],
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
