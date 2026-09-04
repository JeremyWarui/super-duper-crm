/**
 * The stylesheet covers every class name the components reach for.
 *
 * The ported markup places itself with Tailwind utility names, and Tailwind is
 * not installed. src/index.css supplies exactly those names. Nothing here fails
 * loudly at runtime when one is missing: the element simply does not lay out,
 * which is how the sign-in inputs came to sit over the edge of their card.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const src = (path) => readFileSync(resolve(process.cwd(), "src", path), "utf8");

const SOURCES = ["App.jsx", "main.jsx", "components/Login.jsx", "components/Onboarding.jsx"];
const STYLESHEET = src("index.css");

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
    expect(missing, `src/index.css is missing ${missing.join(", ")}`).toEqual([]);
  });

  it("defines nothing the components do not use", () => {
    /* Dead rules are how a stylesheet turns into a framework nobody chose. */
    const used = new Set(classesUsed());
    const unused = [...classesDefined()].filter((name) => !used.has(name));
    expect(unused, `src/index.css defines unused ${unused.join(", ")}`).toEqual([]);
  });

  it("borders and padding count inside an element's width", () => {
    /* Without this the sign-in inputs are wider than the card holding them. */
    expect(STYLESHEET).toMatch(/box-sizing:\s*border-box/);
    expect(STYLESHEET).toMatch(/^\*,/m);
  });

  it("lets the dark rail reach the edge of the window", () => {
    expect(STYLESHEET).toMatch(/body\s*\{[^}]*margin:\s*0/);
  });

  it("gives the app something to be full height against", () => {
    /* App.jsx asks its root for min-height 100%, which needs a parent height. */
    expect(src("App.jsx")).toContain('minHeight: "100%"');
    expect(STYLESHEET).toMatch(/#root\s*\{[^}]*min-height:\s*100vh/);
  });

  it("is loaded once, at the entry point", () => {
    expect(src("main.jsx")).toContain('import "./index.css"');
    for (const file of SOURCES.filter((f) => f !== "main.jsx")) {
      expect(src(file)).not.toContain("index.css");
    }
  });

  it("loads the display faces from the document head", () => {
    /* Both files @import them too; from the head they are up on first paint. */
    const html = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
    expect(html).toContain("fonts.googleapis.com");
    expect(html).toMatch(/family=Oswald/);
    expect(html).toMatch(/family=Inter/);
  });

  it("drops the overview to one column on a narrow screen", () => {
    expect(STYLESHEET).toMatch(/@media\s*\(max-width:\s*720px\)/);
  });
});

describe("fitting the design to the window", () => {
  const app = src("App.jsx");

  it("still identifies the shell by the classes it carries", () => {
    /* The stylesheet reaches the rail and the page through
     * `.mx-auto:not(.flex)`. It holds only while the shell has mx-auto and no
     * flex, and the top rail above it has both. */
    expect(app).toContain('className="mx-auto" style={{ maxWidth: 1200, display: "flex" }}');
    expect(app).toMatch(/className="mx-auto flex[^"]*" style=\{\{ maxWidth: 1200 \}\}/);
  });

  it("still has the rail first and the page second inside the shell", () => {
    /* first-child is the 210px rail, last-child the page beside it. */
    const shell = app.slice(app.indexOf('className="mx-auto" style={{ maxWidth: 1200'));
    const rail = shell.indexOf("width: 210, flexShrink: 0");
    const page = shell.indexOf("flex: 1, minWidth: 0");
    expect(rail).toBeGreaterThan(-1);
    expect(page).toBeGreaterThan(rail);
  });

  it("leaves the drawing untouched at the width it was drawn for", () => {
    /* Every scale rule is behind a max-width, so 1440 and up gets none. */
    const zooms = [...STYLESHEET.matchAll(/@media\s*\(([^)]+)\)\s*\{[^@]*?zoom:/g)];
    expect(zooms.length).toBeGreaterThan(0);
    for (const [, condition] of zooms) {
      expect(condition, `${condition} would scale a large screen`).toContain("max-width");
    }
  });

  it("scales down as the window narrows, never up", () => {
    const tiers = [...STYLESHEET.matchAll(/@media\s*\(max-width:\s*(\d+)px\)\s*\{\s*#root\s*\{\s*zoom:\s*([\d.]+)/g)]
      .map(([, width, zoom]) => ({ width: Number(width), zoom: Number(zoom) }));
    expect(tiers.length).toBeGreaterThanOrEqual(3);
    for (const tier of tiers) {
      expect(tier.zoom).toBeGreaterThan(0.5);
      expect(tier.zoom).toBeLessThanOrEqual(1);
    }
  });

  it("stacks the rail above the page on a narrow screen", () => {
    expect(STYLESHEET).toMatch(/@media\s*\(max-width:\s*860px\)/);
    expect(STYLESHEET).toMatch(/\.mx-auto:not\(\.flex\)\s*\{\s*display:\s*block\s*!important/);
  });

  it("turns the stacked nav into a row that scrolls", () => {
    /* Otherwise seven nav items wrap into a wall above every page. */
    expect(STYLESHEET).toMatch(/flex-direction:\s*row\s*!important/);
    expect(STYLESHEET).toMatch(/overflow-x:\s*auto/);
  });

  it("paints the body the same paper as the page", () => {
    /* A scaled page does not reach the edge; the gap must not read as white. */
    expect(STYLESHEET).toMatch(/body\s*\{[^}]*background:\s*#e9ebe6/i);
    expect(app).toContain('paper: "#E9EBE6"');
  });

  it("asks the browser to use the device width", () => {
    const html = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
    expect(html).toContain("width=device-width");
  });
});

describe("filling a wide window", () => {
  it("lets the shell past the 1200px the design was drawn at", () => {
    /* 1200 of 1920 is the page adrift in 700px of empty paper. */
    expect(src("App.jsx")).toContain("maxWidth: 1200");
    expect(STYLESHEET).toMatch(/@media\s*\(min-width:\s*1441px\)/);
    expect(STYLESHEET).toMatch(/max-width:\s*min\(1720px,\s*calc\(100vw - 96px\)\)\s*!important/);
  });

  it("keeps a gutter rather than running to the edge", () => {
    const [, gutter] = STYLESHEET.match(/calc\(100vw - (\d+)px\)/);
    expect(Number(gutter)).toBeGreaterThan(0);
  });

  it("widens only above the width the scale tiers cover", () => {
    /* Below 1441 the cap stays at 1200 and the tiers scale instead; widening a
     * 1366 laptop is what made it cramped. */
    const widen = STYLESHEET.indexOf("min-width: 1441px");
    expect(widen).toBeGreaterThan(-1);
    const zoomTiers = [...STYLESHEET.matchAll(/@media\s*\(max-width:\s*(\d+)px\)\s*\{\s*#root\s*\{\s*zoom:/g)];
    for (const [, width] of zoomTiers) {
      expect(Number(width)).toBeLessThan(1441);
    }
  });
});
