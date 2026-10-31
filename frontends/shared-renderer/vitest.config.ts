/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * Vitest config for @companion-x/shared-renderer.
 *
 * Hosts the renderer canaries moved out of next-dashboard
 * (component-map, prop-aliases, chart-defensive, style-passthrough)
 * plus the new BridgeAdapter + useToolData seam tests. jsdom +
 * @testing-library/react, mirroring the next-dashboard harness.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom", "react/jsx-runtime"],
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/test/**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", "lib/**"],
    css: false,
  },
});
