/** The component stylesheets cover every class name the components use. */
import { globSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const src = (path) => readFileSync(resolve(process.cwd(), "src", path), "utf8");

// Read off the tree rather than listed: a component added later is covered
// without anybody remembering to add it here, which is how Admin.jsx shipped
// using three class names the stylesheet had never heard of.
const SOURCES = globSync("**/*.jsx", { cwd: resolve(process.cwd(), "src") })
  .map((path) => path.replaceAll("\\", "/"))
  .sort();
const STYLESHEET = globSync("**/*.css", {
  cwd: resolve(process.cwd(), "src"),
})
  .map((path) => src(path))
  .join("\n");

function classesUsed() {
  const found = new Set();
  for (const file of SOURCES) {
    for (const [, value] of src(file).matchAll(/className="([^"]+)"/g)) {
      for (const name of value.split(/\s+/).filter(Boolean)) {
        found.add(name);
      }
    }
  }
  return [...found].sort();
}

function classesDefined() {
  const found = new Set();
  for (const [, name] of STYLESHEET.matchAll(/^\.([a-zA-Z0-9_-]+)\s*[,{]/gm)) {
    found.add(name);
  }
  return found;
}

describe("the stylesheet", () => {
  it("defines every class the components use", () => {
    const defined = classesDefined();
    const missing = classesUsed().filter((name) => !defined.has(name));
    expect(missing, `src/index.css is missing ${missing.join(", ")}`).toEqual(
      [],
    );
  });

});

/* The minifier must not rewrite the media queries into range syntax.
 *
 * esbuild turns `max-width: 860px` into `width<=860px` when the build target
 * allows it. Safari parses that from 16.4; an iPhone 7 stops at iOS 15, drops
 * the whole query as invalid, and renders the desktop layout on a phone.
 * `build.cssTarget` in vite.config.js is what holds this.
 */
