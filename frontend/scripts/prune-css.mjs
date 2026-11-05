// Removes the index.css rules that name any of the given legacy classes.
//   node scripts/prune-css.mjs [--dry-run] <class> [<class> ...]
// A selector goes when it names a listed class exactly; a rule goes when none of its selectors are left.
import { readFileSync, writeFileSync } from "node:fs";
import postcss from "postcss";
const args = process.argv.slice(2);
const dry = args[0] === "--dry-run";
const names = dry ? args.slice(1) : args;
const file = new URL("../src/index.css", import.meta.url);
const dead = new Set(names);
const isDead = (s) => [...s.matchAll(/\.([\w-]+)/g)].some(([, c]) => dead.has(c));
const root = postcss.parse(readFileSync(file, "utf8"));
let n = 0;
root.walkRules((rule) => {
  const keep = rule.selectors.filter((s) => !isDead(s));
  if (keep.length === rule.selectors.length) return;
  n += rule.selectors.length - keep.length;
  if (keep.length) rule.selectors = keep; else rule.remove();
});
root.walkAtRules((a) => { if (a.nodes && a.nodes.length === 0) a.remove(); });
if (!dry) writeFileSync(file, root.toString());
console.log(`${dry ? "would remove" : "removed"} ${n} selectors`);
