/**
 * Every request the app makes, read by parsing the source.
 *
 * A call is read only when it is written plainly: the transport called directly,
 * by the name it was imported under, with a string or template literal for the
 * path, and at most an object literal of options whose `method` is a literal.
 * Anything else is reported as a problem, never guessed at.
 */
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { parseAst } from "rollup/parseAst";

const SOURCE_FILE = /\.(?:js|jsx|mjs|cjs)$/;

/** Every source file under `root`, by absolute path. */
export function sourceFiles(root) {
  const found = [];
  const walkDir = (at) => {
    for (const entry of readdirSync(at, { withFileTypes: true })) {
      const path = join(at, entry.name);
      if (entry.isDirectory()) walkDir(path);
      else if (SOURCE_FILE.test(entry.name)) found.push(path);
    }
  };
  walkDir(root);
  return found.sort();
}

/** Whether an import specifier written in `file` names the transport module. */
function isTransport(specifier, file, transport) {
  if (typeof specifier !== "string" || !specifier.startsWith(".")) return false;
  const target = resolve(dirname(file), specifier).replace(SOURCE_FILE, "");
  return target === resolve(transport).replace(SOURCE_FILE, "");
}

function lineOf(code, offset) {
  let line = 1;
  for (let i = 0; i < offset; i += 1) if (code[i] === "\n") line += 1;
  return line;
}

function walk(node, parent, visit) {
  if (!node || typeof node.type !== "string") return;
  visit(node, parent);
  for (const key of Object.keys(node)) {
    if (key === "start" || key === "end") continue;
    const value = node[key];
    if (Array.isArray(value))
      for (const child of value) walk(child, node, visit);
    else if (value && typeof value.type === "string") walk(value, node, visit);
  }
}

const stripQuery = (path) => path.replace(/\?.*$/, "");

/** The route a path argument names, each expression spelt `{id}`, or null. */
function readPath(node) {
  if (node.type === "Literal" && typeof node.value === "string")
    return stripQuery(node.value);
  if (node.type !== "TemplateLiteral") return null;
  let text = "";
  node.quasis.forEach((quasi, i) => {
    text += quasi.value.cooked ?? quasi.value.raw;
    const expression = node.expressions[i];
    if (!expression) return;
    // The auth store prefixes its own base URL, which is not part of the route.
    const isBase =
      text === "" &&
      expression.type === "Identifier" &&
      expression.name === "BASE";
    if (!isBase) text += "{id}";
  });
  return stripQuery(text);
}

/** The method an options argument asks for, or null when it cannot be read. */
function readMethod(node) {
  if (node.type !== "ObjectExpression") return null;
  let method = "GET";
  for (const property of node.properties) {
    if (property.type !== "Property") return null;
    if (property.computed || property.kind !== "init" || property.method)
      return null;
    const key =
      property.key.type === "Identifier"
        ? property.key.name
        : property.key.value;
    if (key !== "method") continue;
    const { value } = property;
    if (value.type === "Literal" && typeof value.value === "string")
      method = value.value;
    else if (value.type === "TemplateLiteral" && value.expressions.length === 0)
      method = value.quasis[0].value.cooked;
    else return null;
  }
  return /^[A-Z]+$/.test(method) ? method : null;
}

/** `{ method, path }` for one call, or a phrase saying why it cannot be read. */
function readCall(call) {
  if (call.optional) return "is called optionally";
  if (call.arguments.length === 0 || call.arguments.length > 2)
    return "is not called with a path and at most one options object";
  const path = readPath(call.arguments[0]);
  if (path === null)
    return "has a path that is not one string or template literal";
  if (!/^\/[a-z]/.test(path) || !path.endsWith("/"))
    return `has a path that is not a route: ${path}`;
  const method =
    call.arguments.length === 2 ? readMethod(call.arguments[1]) : "GET";
  if (method === null)
    return "has options that are not an object literal with a literal method";
  return { method, path };
}

/** Whether `node` is the name a declaration binds, rather than a use of it. */
function declares(node, parent) {
  if (parent.type === "VariableDeclarator") return parent.id === node;
  if (parent.type === "CatchClause") return parent.param === node;
  if (parent.type === "ClassDeclaration" || parent.type === "ClassExpression")
    return parent.id === node;
  if (parent.type.includes("Function"))
    return parent.id === node || parent.params.includes(node);
  return false;
}

/**
 * Read one file. `fetchAllowed` says whether this file may call `fetch` itself.
 * Returns the calls it read and the problems it found, each with its line.
 */
export function analyseSource(code, { file, transport, fetchAllowed = false }) {
  const calls = [];
  const problems = [];
  const report = (node, message) =>
    problems.push({ file, line: lineOf(code, node.start), message });

  let ast;
  try {
    ast = parseAst(code, { jsx: true });
  } catch (error) {
    problems.push({
      file,
      line: 0,
      message: `cannot be parsed: ${error.message.split("\n")[0]}`,
    });
    return { calls, problems };
  }

  // The names the transport goes by in this file.
  const names = new Set(fetchAllowed ? ["fetch"] : []);
  walk(ast, null, (node) => {
    if (
      node.type !== "ImportDeclaration" ||
      !isTransport(node.source.value, file, transport)
    )
      return;
    for (const specifier of node.specifiers) {
      const imported = specifier.imported?.name ?? specifier.imported?.value;
      if (specifier.type === "ImportSpecifier" && imported === "api")
        names.add(specifier.local.name);
      else if (specifier.type !== "ImportSpecifier")
        report(specifier, "imports the transport other than by name");
    }
  });

  // Names a local declaration takes back; a call through one is not a request.
  const shadowed = new Set();
  walk(ast, null, (node, parent) => {
    if (node.type === "ImportExpression") {
      if (
        node.source.type !== "Literal" ||
        isTransport(node.source.value, file, transport)
      )
        report(node, "imports a module this checker cannot follow");
      return;
    }
    if (
      (node.type === "ExportNamedDeclaration" ||
        node.type === "ExportAllDeclaration") &&
      node.source &&
      isTransport(node.source.value, file, transport)
    ) {
      report(node, "re-exports the transport");
      return;
    }
    if (node.type === "ExportSpecifier" && names.has(node.local.name)) {
      report(node, "hands the transport to another module");
      return;
    }
    if (node.type === "Identifier" && node.name === "XMLHttpRequest") {
      report(node, "makes a request outside the transport");
      return;
    }
    if (
      node.type === "MemberExpression" &&
      !node.computed &&
      node.property.name === "fetch"
    ) {
      report(node, "calls fetch outside the transport");
      return;
    }
    if (node.type !== "Identifier" || !parent) return;
    if (!names.has(node.name) && node.name !== "fetch") return;

    if (parent.type === "ImportSpecifier" || parent.type === "ExportSpecifier")
      return;
    if (
      parent.type === "MemberExpression" &&
      parent.property === node &&
      !parent.computed
    )
      return;
    if (
      parent.type === "Property" &&
      parent.key === node &&
      !parent.computed &&
      !parent.shorthand
    )
      return;

    if (node.name === "fetch" && !fetchAllowed) {
      report(node, "calls fetch outside the transport");
      return;
    }
    if (declares(node, parent)) {
      shadowed.add(node.name);
      report(node, `declares a name the transport goes by: ${node.name}`);
      return;
    }
    if (parent.type === "CallExpression" && parent.callee === node) {
      const read = readCall(parent);
      if (typeof read === "string") report(parent, `${node.name}(...) ${read}`);
      else
        calls.push({
          ...read,
          file,
          line: lineOf(code, parent.start),
          via: node.name,
        });
      return;
    }
    report(
      node,
      `uses ${node.name} as a value, so the request it makes cannot be read`,
    );
  });

  return {
    calls: calls.filter((call) => !shadowed.has(call.via)),
    problems,
  };
}

/** Read every source file under `root` except the transport itself. */
export function surveyCalls({ root, transport, fetchAllowedIn = [] }) {
  const allowed = new Set(fetchAllowedIn.map((path) => resolve(path)));
  const calls = [];
  const problems = [];
  for (const file of sourceFiles(root)) {
    if (resolve(file) === resolve(transport)) continue;
    const result = analyseSource(readFileSync(file, "utf8"), {
      file,
      transport,
      fetchAllowed: allowed.has(resolve(file)),
    });
    calls.push(...result.calls);
    problems.push(...result.problems);
  }
  return { calls, problems };
}
