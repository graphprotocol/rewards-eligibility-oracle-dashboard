import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Two build targets from one component tree:
 *
 *   BUILD_TARGET=ssr     → dist-ssr/entry-server.js, run by the prerenderer.
 *                          Fully bundled (ssr.noExternal), so the runtime image
 *                          needs a node binary but no node_modules. It also
 *                          sidesteps the gds-react barrel importing a .png,
 *                          which bare Node refuses to load.
 *   BUILD_TARGET=client  → ../output/app.js, which hydrates the page.
 */
const isSSR = process.env.BUILD_TARGET !== 'client'

export default defineConfig({
  plugins: [react()],
  // DEV=1 pulls React's development build so hydration errors are readable.
  ssr: { noExternal: true },
  build: isSSR
    ? {
        ssr: 'src/entry-server.jsx',
        outDir: 'dist-ssr',
        assetsInlineLimit: Number.MAX_SAFE_INTEGER,
        emptyOutDir: true,
      }
    : {
        // The Docker build redirects this into the build stage's `out/` dir,
        // which ships to the runtime image and is copied into the output dir
        // alongside gds.css and the fonts.
        outDir: process.env.REO_CLIENT_OUT_DIR ?? '../output',
        emptyOutDir: false, // index.html and gds.css live here too
        assetsInlineLimit: Number.MAX_SAFE_INTEGER,
        minify: !process.env.DEV,
        rollupOptions: {
          input: 'src/entry-client.jsx',
          output: {
            entryFileNames: 'app.js',
            assetFileNames: 'app.[ext]',
            // One file keeps the <script> wiring in prerender.mjs trivial.
            manualChunks: undefined,
            codeSplitting: false,
          },
        },
      },
})
