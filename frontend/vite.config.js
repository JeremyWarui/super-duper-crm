import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: { proxy: { "/api": "http://localhost:8000" } },
  build: {
    outDir: "dist",
    // Tailwind CSS v4 needs Safari 16.4 or later; iOS 15 is not supported.
    cssTarget: ["safari16.4", "chrome111", "firefox128", "edge111"],
  },
  // Dev and build transform JSX through oxc, which needs no setting. Vitest
  // runs the test files through esbuild, which defaults to the classic runtime
  // and would want React in scope. Setting it outside test mode only earns a
  // warning that the option is being ignored.
  ...(mode === "test" ? { esbuild: { jsx: "automatic" } } : {}),
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./tests/setup.js",
    include: ["tests/**/*.test.{js,jsx}"],
    // A userEvent test that types through a form takes about two seconds here,
    // and several seconds on a loaded machine. The 5s default leaves no room
    // and the suite fails on timing rather than on behaviour.
    testTimeout: 20_000,
    hookTimeout: 20_000,
  },
}));
