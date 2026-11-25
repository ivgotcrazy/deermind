import { fileURLToPath, URL } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import vue from '@vitejs/plugin-vue';
import { defineConfig, loadEnv } from 'vite';

// Separate HTML entries share dependencies, styles and build settings.
export default defineConfig(({ mode }) => {
  const api = loadEnv(mode, '.', 'M1_').M1_API_TARGET || 'http://127.0.0.1:8000';
  return {
    plugins: [vue(), tailwindcss()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      proxy: {
        '/api/m1': { target: api },
        '/ws': { target: api, ws: true },
      },
    },
    build: {
      rollupOptions: {
        input: {
          admin: 'admin/index.html',
          student: 'student/index.html',
        },
      },
    },
  };
});
