import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Read VITE_API_TARGET from .env files without depending on @types/node.
  const env = loadEnv(mode, '.', '');

  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      // Proxy /api to the backend so the browser sees a single origin and no
      // CORS preflight is needed in development. Listen on LAN so Harmony
      // guests can open the share URL. LAN browsers can unlock Nous with
      // the admin password; Harmony guest accounts still cannot.
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          xfwd: true,
          timeout: 0,
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq, req) => {
              const host = req.headers.host;
              if (host) {
                proxyReq.setHeader('X-Forwarded-Host', String(host));
              }
            });
            proxy.on('proxyRes', (proxyRes, req) => {
              const url = 'url' in req ? String(req.url || '') : '';
              if (url.includes('/chat/stream') || url.includes('/assistant/ask/stream')) {
                proxyRes.headers['cache-control'] = 'no-cache, no-transform';
                proxyRes.headers['x-accel-buffering'] = 'no';
              }
            });
          },
        },
        '/harmony': {
          target: 'http://127.0.0.1:5174',
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  };
});
