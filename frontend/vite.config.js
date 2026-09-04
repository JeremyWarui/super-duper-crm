import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: { outDir: "dist" },
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
  },
}));
