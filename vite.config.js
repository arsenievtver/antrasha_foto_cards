import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  /** Как dev: чтобы `vite preview` и локальный билд ходили в API через тот же префикс `/api`. */
  preview: {
    host: "0.0.0.0",
    port: 4173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/internal": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  server: {
    // Слушаем все интерфейсы — удобно открывать с телефона по Wi‑Fi (http://192.168.x.x:5173)
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Иначе Vite может отклонять запросы с заголовком Host = LAN‑IP
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/internal": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
})