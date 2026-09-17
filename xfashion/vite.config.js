import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function siteOriginInHtml(env) {
  const origin = (env.VITE_SITE_ORIGIN || "https://xfashion.pro").replace(/\/$/, "");
  return {
    name: "xfashion-site-origin-html",
    transformIndexHtml(html) {
      return html.replaceAll("__XF_SITE_ORIGIN__", origin);
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
  plugins: [react(), siteOriginInHtml(env)],
  preview: {
    host: "0.0.0.0",
    port: 4176,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5176,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
};
});
