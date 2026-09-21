import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// FIX #14: Removed kimi-plugin-inspect-react — it is a non-standard plugin
// auto-injected by the Kimi AI code generator and serves no purpose in the app.
// Keeping only the standard @vitejs/plugin-react plugin.
export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});