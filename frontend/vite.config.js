import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: './',
  publicDir: 'public',
  server: {
    port: 5173,
    open: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8069',
        changeOrigin: true,
      },
      '/avatar': {
        target: 'http://localhost:8069',
        changeOrigin: true,
      },
      '/generate': {
        target: 'http://localhost:9500',
        changeOrigin: true,
      },
      '/output': {
        target: 'http://localhost:9500',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    minify: 'esbuild',
  },
});
