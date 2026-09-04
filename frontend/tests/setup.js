import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";
import { useAuth } from "../src/store/auth";

beforeEach(() => {
  localStorage.clear();
  useAuth.setState({ token: null, user: null });
});

afterEach(() => {
  cleanup();
});
