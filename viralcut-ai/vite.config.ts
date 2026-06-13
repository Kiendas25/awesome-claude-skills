import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { viteSingleFile } from 'vite-plugin-singlefile';

// STANDALONE=1 produces a single, fully self-contained index.html with all JS
// and CSS inlined and NO external network requests — ideal for opening directly
// from the iPhone Files app or hosting anywhere with zero config.
const standalone = process.env.STANDALONE === '1';

// FFmpeg.wasm (multi-threaded build) needs cross-origin isolation.
// These headers enable SharedArrayBuffer in dev and preview.
const crossOriginIsolation = {
  name: 'cross-origin-isolation',
  configureServer(server: any) {
    server.middlewares.use((_req: any, res: any, next: any) => {
      res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
      res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
      next();
    });
  },
  configurePreviewServer(server: any) {
    server.middlewares.use((_req: any, res: any, next: any) => {
      res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
      res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
      next();
    });
  },
};

export default defineConfig({
  plugins: standalone
    ? [react(), viteSingleFile()]
    : [
        react(),
        crossOriginIsolation,
        VitePWA({
          registerType: 'autoUpdate',
          includeAssets: ['favicon.svg'],
          manifest: {
            name: 'ViralCut AI',
            short_name: 'ViralCut',
            description: 'Free local-first short-form video editor.',
            theme_color: '#0b0b12',
            background_color: '#0b0b12',
            display: 'standalone',
            orientation: 'portrait',
            icons: [
              {
                src: 'icon-192.svg',
                sizes: '192x192',
                type: 'image/svg+xml',
                purpose: 'any maskable',
              },
              {
                src: 'icon-512.svg',
                sizes: '512x512',
                type: 'image/svg+xml',
                purpose: 'any maskable',
              },
            ],
          },
          workbox: {
            maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
            globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
          },
        }),
      ],
  build: {
    outDir: standalone ? 'dist-standalone' : 'dist',
    // Inline everything for the single-file build.
    assetsInlineLimit: standalone ? 100_000_000 : 4096,
    cssCodeSplit: !standalone,
  },
  optimizeDeps: {
    exclude: ['@ffmpeg/ffmpeg', '@ffmpeg/util'],
  },
  server: {
    host: true,
  },
});
