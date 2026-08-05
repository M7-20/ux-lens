// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// Single knob for platform integration (waha ONBOARDING.md §2) — unset in local dev,
// the app serves from "/" exactly as before. Set VITE_BASE_PATH=/uxlens/ when deploying
// behind the platform gateway; TanStack Start derives the router's basepath from this
// automatically (see @tanstack/start-plugin-core's deriveRouterBasepath).
const basePath = process.env.VITE_BASE_PATH || "/";

export default defineConfig({
  vite: { base: basePath },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
