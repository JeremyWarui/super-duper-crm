import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";
import { useAuth } from "../src/store/auth";

// A findBy waits up to five seconds: on a loaded machine the first render of a route can take
// longer than the one-second default, and the test would fail on timing, not behaviour.
configure({ asyncUtilTimeout: 5000 });

// jsdom lacks what Radix menus measure and capture with.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => {};
Element.prototype.scrollIntoView ??= () => {};

// jsdom lacks the layout calls the post text editor (ProseMirror) makes on a click.
document.elementFromPoint ??= () => null;
Range.prototype.getClientRects ??= () => [];
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

beforeEach(() => {
  localStorage.clear();
  useAuth.setState({ token: null, user: null });
});

afterEach(() => {
  cleanup();
});
