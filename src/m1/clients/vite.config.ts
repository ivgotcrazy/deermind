import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

// Separate HTML entries share dependencies, styles and build settings.
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      input: {
        admin: 'admin/index.html',
        student: 'student/index.html',
      },
    },
  },
});
