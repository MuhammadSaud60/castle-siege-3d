import { defineConfig } from 'vite';

export default defineConfig({
  // Relative base so the built site works served from any path (Render static).
  base: './',
  build: {
    outDir: 'dist',
  },
  server: {
    port: 5173,
  },
  preview: {
    port: 4173,
  },
});
