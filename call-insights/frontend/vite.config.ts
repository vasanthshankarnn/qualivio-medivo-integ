import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

// The UI calls its own origin (/v1/...); Vite forwards to the FastAPI service, so no CORS setup is needed.
const API_TARGET = process.env.CI_API_TARGET ?? 'http://127.0.0.1:8010';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: { '/v1': { target: API_TARGET, changeOrigin: true } },
  },
});
