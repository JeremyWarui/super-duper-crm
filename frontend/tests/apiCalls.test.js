/** The request reader: what it reads, and what it refuses to guess at. */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { analyseSource, sourceFiles, surveyCalls } from "./apiCalls";

const TRANSPORT = "/app/src/api/client.js";
const HOOKS = "/app/src/api/hooks.js";
const COMPONENT = "/app/src/components/Panel.jsx";
const AUTH = "/app/src/store/auth.js";
const IMPORT = 'import { api } from "./client";\n';

const read = (code, file = HOOKS, fetchAllowed = false) =>
  analyseSource(code, { file, transport: TRANSPORT, fetchAllowed });
const routes = (result) =>
  result.calls.map((call) => `${call.method} ${call.path}`);

function expectRead(code, expected, file = HOOKS, fetchAllowed = false) {
  const result = read(code, file, fetchAllowed);
  expect(result.problems).toEqual([]);
  expect(routes(result)).toEqual(expected);
}

function expectRefused(code, file = HOOKS) {
  const result = read(code, file);
  expect(
    result.problems.length,
    `should have been refused:\n${code}`,
  ).toBeGreaterThan(0);
  return result;
}

describe("the calls it reads", () => {
  it("a literal path", () => {
    expectRead(`${IMPORT}export const a = () => api("/wards/");`, [
      "GET /wards/",
    ]);
  });

  it("a template path, dropping the query string", () => {
    expectRead(
      `${IMPORT}export const b = (id) => api(\`/targets/?campaign=\${id}\`);`,
      ["GET /targets/"],
    );
  });

  it("a literal method beside a shorthand body", () => {
    expectRead(
      `${IMPORT}export const c = (body) => api("/events/", { method: "POST", body });`,
      ["POST /events/"],
    );
  });

  it("optional chaining and ?? inside the path", () => {
    expectRead(
      `${IMPORT}export const d = (t, u) => api(\`/targets/\${t?.id ?? u}/\`, { method: "PATCH" });`,
      ["PATCH /targets/{id}/"],
    );
  });

  it("a call split across lines", () => {
    expectRead(
      `${IMPORT}export const e = () =>\n  api(\n    "/campaigns/",\n    {\n      method: "POST",\n    },\n  );`,
      ["POST /campaigns/"],
    );
  });

  it("comments and strings that mention the transport", () => {
    expectRead(
      `${IMPORT}// api("/nope/") would fetch the wards once\n/* fetch("/x/") */\n` +
        'export const f = () => api("/wards/", { method: "GET", body: { note: "done :) fetch" } });',
      ["GET /wards/"],
    );
  });

  it("the top-level method, not one nested in the body", () => {
    expectRead(
      `${IMPORT}export const g = () => api("/events/", { body: { method: "GET" }, method: "DELETE" });`,
      ["DELETE /events/"],
    );
  });

  it("a quoted method key", () => {
    expectRead(
      `${IMPORT}export const h = () => api("/events/", { "method": "DELETE" });`,
      ["DELETE /events/"],
    );
  });

  it("the transport imported under another name", () => {
    expectRead(
      'import { api as request } from "./client";\nexport const i = () => request("/wards/");',
      ["GET /wards/"],
    );
  });

  it("a component importing the transport by its path", () => {
    expectRead(
      'import { api } from "../api/client";\nexport const j = () => api("/counties/");',
      ["GET /counties/"],
      COMPONENT,
    );
  });

  it("a call inside a JSX attribute", () => {
    expectRead(
      'import { api } from "../api/client";\nexport const K = () => <button onClick={() => api("/wards/")}>go</button>;',
      ["GET /wards/"],
      COMPONENT,
    );
  });

  it("the auth store's own fetch, without its base URL", () => {
    expectRead(
      'const BASE = "http://x";\n' +
        'export const login = () => fetch(`${BASE}/auth/login/`, { method: "POST", headers: { "Content-Type": "application/json" } });',
      ["POST /auth/login/"],
      AUTH,
      true,
    );
  });
});

describe("the calls it refuses rather than misreads", () => {
  it("a path built with +", () => {
    expectRefused(
      `${IMPORT}export const a = (id) => api("/campaigns/" + id + "/");`,
    );
  });

  it("a path held in a variable", () => {
    expectRefused(
      `${IMPORT}const path = "/mobilizers/";\nexport const b = () => api(path, { method: "DELETE" });`,
    );
  });

  it("a method held in a variable", () => {
    const result = expectRefused(
      `${IMPORT}const verb = "DELETE";\nexport const c = () => api("/admin/users/", { method: verb });`,
    );
    expect(routes(result)).not.toContain("GET /admin/users/");
  });

  it("a shorthand method", () => {
    const result = expectRefused(
      `${IMPORT}export const d = (method) => api("/campaigns/", { method });`,
    );
    expect(routes(result)).not.toContain("GET /campaigns/");
  });

  it("options held in a variable", () => {
    const result = expectRefused(
      `${IMPORT}const opts = { method: "DELETE" };\nexport const e = () => api("/campaigns/", opts);`,
    );
    expect(routes(result)).not.toContain("GET /campaigns/");
  });

  it("options spread in", () => {
    const result = expectRefused(
      `${IMPORT}const del = { method: "DELETE" };\nexport const f = () => api("/campaigns/", { ...del });`,
    );
    expect(routes(result)).not.toContain("GET /campaigns/");
  });

  it("options built by a helper", () => {
    const result = expectRefused(
      `${IMPORT}const post = (body) => ({ method: "POST", body });\nexport const g = (b) => api("/wards/", post(b));`,
    );
    expect(routes(result)).not.toContain("GET /wards/");
  });

  it("the transport handed to another name", () => {
    expectRefused(
      `${IMPORT}const call = api;\nexport const h = () => call("/secret/everything/");`,
    );
  });

  it("the transport passed as a value", () => {
    expectRefused(`${IMPORT}export const i = { queryFn: api };`);
  });

  it("the transport called through .call", () => {
    expectRefused(`${IMPORT}export const j = () => api.call(null, "/wards/");`);
  });

  it("the transport called optionally", () => {
    expectRefused(`${IMPORT}export const k = () => api?.("/wards/");`);
  });

  it("the transport re-exported under another name", () => {
    expectRefused(`${IMPORT}export { api as remote };`);
  });

  it("the transport re-exported straight from the client", () => {
    expectRefused('export { api } from "./client";');
  });

  it("the transport renamed, then handed to another module", () => {
    expectRefused(
      'import { api as remote } from "./client";\nexport { remote };',
    );
  });

  it("the client imported as a namespace", () => {
    expectRefused(
      'import * as client from "./client";\nexport const l = () => client.api("/wards/");',
    );
  });

  it("the client imported dynamically", () => {
    expectRefused(
      'export const m = async () => (await import("./client")).api("/wards/");',
    );
  });

  it("a module imported by a name computed at run time", () => {
    expectRefused("export const n = (name) => import(name);");
  });

  it("fetch called from a component", () => {
    expectRefused('export const o = () => fetch("/api/wards/");', COMPONENT);
  });

  it("fetch reached through globalThis", () => {
    expectRefused(
      'export const p = () => globalThis.fetch("/api/wards/");',
      COMPONENT,
    );
  });

  it("an XMLHttpRequest", () => {
    expectRefused("export const q = () => new XMLHttpRequest();", COMPONENT);
  });

  it("a parameter that shadows the transport", () => {
    const result = expectRefused(
      `${IMPORT}export function r(api) {\n  return api("/wards/");\n}`,
    );
    expect(routes(result)).not.toContain("GET /wards/");
  });

  it("source that does not parse", () => {
    expectRefused("export const s = (;");
  });
});

describe("the files it reads", () => {
  function tree(files) {
    const root = mkdtempSync(join(tmpdir(), "apicalls-"));
    for (const [name, code] of Object.entries(files)) {
      mkdirSync(join(root, name, ".."), { recursive: true });
      writeFileSync(join(root, name), code);
    }
    return root;
  }

  it("includes .mjs and .cjs files as well as .js and .jsx", () => {
    const root = tree({
      "a.js": "",
      "b.jsx": "",
      "deep/c.mjs": "",
      "deep/d.cjs": "",
      "e.css": "",
      "f.json": "",
    });
    try {
      const found = sourceFiles(root).map((path) =>
        path.slice(root.length + 1).replaceAll("\\", "/"),
      );
      expect(found).toEqual(["a.js", "b.jsx", "deep/c.mjs", "deep/d.cjs"]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("skips only the transport itself, not every file named like it", () => {
    const root = tree({
      "api/client.js": "export const api = (path) => fetch(path);",
      "vendor/api/client.js":
        'export const leak = () => fetch("/api/everything/");',
    });
    try {
      const result = surveyCalls({
        root,
        transport: join(root, "api", "client.js"),
      });
      expect(result.problems.map((problem) => problem.message)).toContain(
        "calls fetch outside the transport",
      );
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});
