import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    // Plain React plugin. The React Compiler was removed from the dev/build path: it is an
    // optimisation, not a correctness feature, and on Node versions below Vite's minimum it
    // could emit transformed code that failed silently in the browser. The app has no manual
    // useMemo/useCallback either way, so nothing depends on it.
    react(),
    tailwindcss(),
  ],
  build: {
    rollupOptions: {
      // Two entries: the landing page is static HTML with its own inline motion script and
      // pulls in no framework at all, so it stays out of the React bundle entirely. The
      // reader is the React app.
      input: {
        main: resolve(__dirname, "index.html"),
        app: resolve(__dirname, "app.html"),
      },
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react/jsx-runtime"],
          query: ["@tanstack/react-query", "@tanstack/react-virtual"],
          // zod runs at the boundary on every response, so it is needed on first paint and
          // is split for caching rather than for deferral.
          schema: ["zod"],
          // motion is deliberately absent: naming it here would defeat the lazy import in
          // components/ui/EnterOnce.tsx and put 27 kB back on the critical path.
        },
      },
    },
  },
});
