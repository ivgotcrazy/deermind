import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  resolve: { dedupe: ['vue'] },
  base: './',
  server: {
    port: 5180,
    host: '0.0.0.0',
  },
});
