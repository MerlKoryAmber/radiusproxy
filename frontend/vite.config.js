import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The /api prefix is proxied to the FastAPI backend during development so the
// frontend and API can be served from the same origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
