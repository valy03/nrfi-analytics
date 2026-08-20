import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Docker Desktop on Windows doesn't reliably forward host filesystem
    // events into the Linux container over the bind mount, so chokidar's
    // default (event-based) watching silently never fires — Vite serves a
    // stale cached transform for an edited file even on a fresh request,
    // not just over the HMR websocket. Polling actually notices changes.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
