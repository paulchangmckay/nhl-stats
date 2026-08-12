import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Fixed name for the entry so templates/index.html can reference it
        // statically. Fonts/other assets keep hashed per-file names below —
        // a prior fixed assetFileNames pattern collided shadcn's 5 Geist
        // font subset files into one, silently breaking non-Latin glyphs.
        entryFileNames: "app.js",
        chunkFileNames: "app-[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          const name = assetInfo.names?.[0] ?? assetInfo.name ?? "";
          return name.endsWith(".css") ? "app.css" : "assets/[name]-[hash][extname]";
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:5099",
    },
  },
});
