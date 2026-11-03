// Full-page screenshots at exact widths through headless Chrome's DevTools protocol.
// Usage: node scripts/screenshot.mjs <out-dir> <name>=<url> [...]   (WIDTHS="1440,390" by default)
// A "localStorage" JSON file in AUTH (optional) is written into each page's origin before loading.
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const WIDTHS = (process.env.WIDTHS || "1440,390").split(",").map(Number);
const [outDir, ...pages] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), "shot-"));
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function target() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      const page = list.find((t) => t.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(200);
  }
  throw new Error("Chrome did not start");
}

const ws = new WebSocket(await target());
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let seq = 0;
const waiting = new Map();
ws.addEventListener("message", (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id && waiting.has(msg.id)) waiting.get(msg.id)(msg);
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++seq;
  waiting.set(id, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
  ws.send(JSON.stringify({ id, method, params }));
});

await send("Page.enable");
const auth = process.env.AUTH ? readFileSync(process.env.AUTH, "utf8") : null;
for (const spec of pages) {
  const [name, url] = spec.split(/=(.*)/s);
  for (const width of WIDTHS) {
    await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 768 });
    if (auth && url.startsWith("http")) {
      await send("Page.navigate", { url: new URL(url).origin + "/signin" });
      await sleep(1500);
      const set = await send("Runtime.evaluate", { expression: `localStorage.setItem("campaign-auth", ${JSON.stringify(auth)}); location.origin` });
      if (set.exceptionDetails) throw new Error(`could not sign in: ${set.exceptionDetails.text}`);
    }
    await send("Page.navigate", { url });
    await sleep(6000);
    const { contentSize } = await send("Page.getLayoutMetrics");
    const height = Math.min(Math.ceil(contentSize.height), 6000);
    const wide = Math.ceil(contentSize.width) > width;
    await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 768 });
    await sleep(300);
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    const file = join(outDir, `${name}_${width}.png`);
    writeFileSync(file, Buffer.from(data, "base64"));
    console.log(`${file}${wide ? `  (page is ${Math.ceil(contentSize.width)}px wide: horizontal scroll)` : ""}`);
  }
}
ws.close();
chrome.kill();
