import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const apiProxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (requestPath) => requestPath.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react()],
  preview: {
    host: "0.0.0.0",
    port: 4177,
    strictPort: true,
    allowedHosts: true,
    proxy: apiProxy,
  },
  server: {
    fs: { allow: [repoRoot] },
    host: "0.0.0.0",
    port: 5177,
    strictPort: true,
    allowedHosts: true,
    proxy: apiProxy,
  },
});
