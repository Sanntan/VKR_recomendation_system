import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "localhost",
    port: 5173,
    proxy: {
      "^/(students|events|bot|recommendations|feedback|favorites|maintenance|health).*": {
        target: API_TARGET,
        changeOrigin: true,
        secure: false
      }
    }
  }
});
