#!/usr/bin/env node
/**
 * tools/ui-audit/shot.mjs — one-off viewport screenshots of an arbitrary state.
 *
 *   node tools/ui-audit/shot.mjs --url http://127.0.0.1:8011 --hash "#research/RELIANCE" \
 *        --viewport 390x844 --scroll "#chart" --out tools/ui-audit/out/chart-390.png
 *   node tools/ui-audit/shot.mjs ... --click "#panelNavToggle" --wait 400
 *
 * Uses the same zero-dependency CDP plumbing as audit.mjs.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Cdp, httpJson, findFreePort, sleep } from "./audit.mjs";

const args = process.argv.slice(2);
const arg = (name, dflt) => {
  const i = args.indexOf("--" + name);
  return i >= 0 ? args[i + 1] : dflt;
};

const URL_ = arg("url", "http://127.0.0.1:8011");
const HASH = arg("hash", "#research");
const VIEWPORT = arg("viewport", "390x844").split("x").map(Number);
const SCROLL = arg("scroll", "");
const CLICK = arg("click", "");
const OUT = arg("out", "tools/ui-audit/out/shot.png");
const WAIT = Number(arg("wait", 6000));
const INJECT_FILE = arg("inject-file", "");
const POST_EXPR_FILE = arg("post-expr-file", "");
const CHROME = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "shot-"));
const port = await findFreePort();
const child = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--hide-scrollbars", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "about:blank",
], { stdio: "ignore" });

async function version() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await httpJson(`http://127.0.0.1:${port}/json/version`, { timeoutMs: 2000 });
      if (r && r.statusCode === 200) return JSON.parse(r.body);
    } catch { /* retry */ }
    await sleep(250);
  }
  throw new Error("chrome never came up");
}

try {
  const v = await version();
  const cdp = await Cdp.connect(v.webSocketDebuggerUrl, 15000);
  const t = await cdp.send("Target.createTarget", { url: "about:blank" });
  const a = await cdp.send("Target.attachToTarget", { targetId: t.targetId, flatten: true });
  const sid = a.sessionId;
  cdp.sessionId = sid;
  await cdp.send("Page.enable", {}, sid);
  await cdp.send("Runtime.enable", {}, sid);
  await cdp.send("Network.enable", {}, sid);
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true }, sid);
  /* No login gate: an Authorization header is sent only when both halves of an
     explicit credential pair are present in ADMIN_USER / ADMIN_PASS. */
  const authUser = process.env.ADMIN_USER || "";
  const authPass = process.env.ADMIN_PASS || "";
  if (authUser && authPass) {
    await cdp.send("Network.setExtraHTTPHeaders", {
      headers: { Authorization: "Basic " + Buffer.from(`${authUser}:${authPass}`).toString("base64") },
    }, sid);
  }
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: VIEWPORT[0], height: VIEWPORT[1], deviceScaleFactor: 1, mobile: VIEWPORT[0] < 768,
  }, sid);
  if (INJECT_FILE) {
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
      source: fs.readFileSync(INJECT_FILE, "utf8"),
      runImmediately: true,
    }, sid);
    console.log("[shot] injected", INJECT_FILE);
  }
  const loaded = new Promise((res) => { const off = cdp.on("Page.loadEventFired", () => { off(); res(); }); });
  await cdp.send("Page.navigate", { url: URL_.replace(/#.*$/, "") + "/?_shot=" + Date.now() + HASH }, sid);
  await Promise.race([loaded, sleep(25000)]);
  await sleep(WAIT);

  if (CLICK) {
    const r = await cdp.send("Runtime.evaluate", {
      expression: `(() => { const el = document.querySelector(${JSON.stringify(CLICK)});
        if (!el) return "no match"; el.click(); return "clicked"; })()`, returnByValue: true,
    }, sid);
    console.log("[shot] click", CLICK, "->", r.result && r.result.value);
    await sleep(700);
  }
  if (POST_EXPR_FILE) {
    const source = fs.readFileSync(POST_EXPR_FILE, "utf8");
    const r = await cdp.send("Runtime.evaluate", {
      expression: source, returnByValue: true, awaitPromise: true,
    }, sid);
    console.log("[shot] post-expr ->", r.result && r.result.value);
    await sleep(900);
  }
  if (SCROLL) {
    const r = await cdp.send("Runtime.evaluate", {
      expression: `(() => { const el = document.querySelector(${JSON.stringify(SCROLL)});
        if (!el) return "no match"; const y = el.getBoundingClientRect().top + window.scrollY - 8;
        window.scrollTo(0, y); return "scrolled to " + Math.round(y); })()`, returnByValue: true,
    }, sid);
    console.log("[shot] scroll", SCROLL, "->", r.result && r.result.value);
    await sleep(900);
  }
  const shot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sid);
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, Buffer.from(shot.data, "base64"));
  console.log("[shot] wrote", OUT, fs.statSync(OUT).size, "bytes");
  await cdp.close();
} finally {
  /* On Windows child.kill() leaves the whole Chrome renderer tree alive.
     audit.mjs already solves this with taskkill /T; do the same here so repeated
     runs cannot pile up orphaned temp-profile browsers. */
  try { child.kill(); } catch {}
  if (child.exitCode === null && process.platform === "win32") {
    try {
      spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        stdio: "ignore", windowsHide: true,
      });
    } catch {}
  }
  await sleep(400);
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
}
