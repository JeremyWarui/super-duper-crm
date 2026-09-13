import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    outDir: "dist",
    // esbuild rewrites `max-width: 860px` to the range syntax `width<=860px`
    // when the target allows it. Safari understands that from 16.4; an
    // iPhone 7 stops at iOS 15, drops the whole query, and renders the
    // desktop layout. Naming the oldest browser we serve keeps the old syntax.
    cssTarget: ["safari15", "chrome90", "firefox90", "edge90"],
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
