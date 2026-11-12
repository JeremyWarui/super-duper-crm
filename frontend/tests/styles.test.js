/** The stylesheet holds only what the components use, and nothing brings back the legacy kit. */
import { globSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import postcss from "postcss";
import { describe, expect, it } from "vitest";

const SRC = resolve(process.cwd(), "src");
const read = (path) => readFileSync(resolve(SRC, path), "utf8");
const SOURCES = globSync("**/*.{js,jsx,ts,tsx}", { cwd: SRC }).map((path) => read(path)).join("\n");
// Class names the rich-text editor adds itself at runtime.
const RUNTIME = /^ProseMirror-/;

function classesDefined() {
  const found = new Set();
  postcss.parse(read("styles/globals.css")).walkRules((rule) => {
    for (const selector of rule.selectors) {
      for (const [, name] of selector.matchAll(/\.([A-Za-z][\w-]*)/g)) found.add(name);
    }
  });
  return [...found].filter((name) => !RUNTIME.test(name)).sort();
}

describe("the stylesheet", () => {
  it("tells browsers the site is light only, so a dark device setting cannot darken it", () => {
    expect(readFileSync(resolve(process.cwd(), "index.html"), "utf8")).toContain('<meta name="color-scheme" content="only light" />');
    expect(read("styles/globals.css")).toMatch(/color-scheme: only light;/);
  });

  it("keeps no rule for a class no component uses", () => {
    const unused = classesDefined().filter((name) => !new RegExp(`["'\`\\s]${name}["'\`\\s]`).test(SOURCES));
    expect(unused, `styles/globals.css styles ${unused.join(", ")}, which nothing uses`).toEqual([]);
  });

  it("has no legacy root or legacy stylesheet to fall back on", () => {
    expect(globSync("**/*.css", { cwd: SRC }).map((path) => path.replaceAll("\\", "/"))).toEqual(["styles/globals.css"]);
    expect(SOURCES).not.toMatch(/className="legacy"|components\/Legacy|index\.css/);
  });
});
