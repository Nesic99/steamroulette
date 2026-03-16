import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Dev proxy: forwards /api to local Flask during `npm run dev`
    proxy: {
      "/api": "http://localhost:5000",
    },
  },
});
