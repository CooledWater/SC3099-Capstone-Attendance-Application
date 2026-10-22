import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  base: process.env.DASHBOARD_BASE_PATH || '/dashboard/',
  server: {
    // Browser API calls stay on the same origin for HttpOnly login cookies.
    proxy: { '/api/v1': { target: process.env.BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true } },
    allowedHosts: ['dashboard', 'localhost'],
    hmr: process.env.DASHBOARD_BASE_PATH ? false : undefined,
  },
  preview: {
    allowedHosts: ['dashboard', 'localhost'],
    proxy: { '/api/v1': { target: process.env.BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
});
