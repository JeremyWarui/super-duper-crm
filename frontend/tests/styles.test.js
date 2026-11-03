/** The component stylesheets cover every class name the components use. */
import { globSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import postcss from "postcss";
import { describe, expect, it } from "vitest";

const src = (path) => readFileSync(resolve(process.cwd(), "src", path), "utf8");

// Read off the tree rather than listed: a component added later is covered
// without anybody remembering to add it here, which is how Admin.jsx shipped
// using three class names the stylesheet had never heard of. A page built on
// the UI kit (it imports kit components and wraps nothing in Legacy) takes
// Tailwind classes, not index.css, and is skipped.
const SOURCES = globSync("**/*.jsx", { cwd: resolve(process.cwd(), "src") })
  .map((path) => path.replaceAll("\\", "/"))
  .filter((path) => !(src(path).includes('from "@/components/') && !src(path).includes("Legacy")))
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
  for (const [, name] of STYLESHEET.matchAll(/^\.(?:legacy \.)?([a-zA-Z0-9_-]+)\s*[,{]/gm)) {
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

  it("styles nothing outside a .legacy root on screen", () => {
    const loose = [];
    postcss.parse(src("index.css")).walkRules((rule) => {
      if (rule.parent.type === "atrule" && rule.parent.params === "print") return;
      loose.push(...rule.selectors.filter((s) => !/^\.legacy\b/.test(s)));
    });
    expect(loose).toEqual([]);
  });

});
