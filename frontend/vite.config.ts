import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy /api → FastAPI backend (avoids CORS). `streamChat` calls `/api/chat`.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
