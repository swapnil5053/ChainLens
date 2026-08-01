import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    // React Compiler v1. Memoisation is the compiler's job; there is no manual useMemo or
    // useCallback in src/ for that purpose, and the verification step greps to keep it so.
    react({ babel: { plugins: [["babel-plugin-react-compiler", {}]] } }),
    tailwindcss(),
  ],
  build: {
    rollupOptions: {
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
