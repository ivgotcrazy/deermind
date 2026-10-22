import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  base: './',
  build: { rollupOptions: { input: { main: fileURLToPath(new URL('./index.html', import.meta.url)), phase4: fileURLToPath(new URL('./phase4.html', import.meta.url)), structure: fileURLToPath(new URL('./structure.html', import.meta.url)), legacyStructure: fileURLToPath(new URL('./legacy-structure.html', import.meta.url)) } } },
  server: { host: '127.0.0.1', port: 5178, strictPort: true },
  preview: { host: '127.0.0.1', port: 5178, strictPort: true },
});
