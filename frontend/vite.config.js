import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  esbuild: { jsx: "automatic" },
  build: { outDir: "dist" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./tests/setup.js",
    include: ["tests/**/*.test.{js,jsx}"],
  },
});
