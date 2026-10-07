#!/usr/bin/env node
/**
 * tools/ui-audit/eval.mjs — run one JS expression in the real page and print the result.
 * Zero-dependency CDP; same plumbing as audit.mjs.
 *
 *   node tools/ui-audit/eval.mjs --hash "#research/KEI" --viewport 390x844 \
 *        --expr "document.querySelectorAll('#chartToolbar button').length"
 *   node tools/ui-audit/eval.mjs --hash "#research/KEI" --click "#patternToggle" \
 *        --expr "document.querySelector('#chartMobileNote').textContent"
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Cdp, httpJson, findFreePort, sleep } from "./audit.mjs";

const args = process.argv.slice(2);
const arg = (n, d) => { const i = args.indexOf("--" + n); return i >= 0 ? args[i + 1] : d; };

const URL_ = arg("url", "http://127.0.0.1:8011");
const HASH = arg("hash", "#research");
const EXPR_FILE = arg("expr-file", "");
/* --inject-file runs the script in an ISOLATED world before any page script
   (via Page.addScriptToEvaluateOnNewDocument). Use it to stub fetch and let the
   real app code path run; it writes nothing to the repo. Such a script reports
   back through window.name, which is readable from the main world. */
const INJECT_FILE = arg("inject-file", "");
const EXPR = EXPR_FILE ? fs.readFileSync(EXPR_FILE, "utf8") : arg("expr", "1+1");
const CLICK = arg("click", "");
const VIEWPORT = arg("viewport", "390x844").split("x").map(Number);
const WAIT = Number(arg("wait", 8000));
const CHROME = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "eval-"));
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
    console.log("[eval] injected", INJECT_FILE);
  }
  const loaded = new Promise((res) => { const off = cdp.on("Page.loadEventFired", () => { off(); res(); }); });
  await cdp.send("Page.navigate", { url: URL_.replace(/#.*$/, "") + "/?_eval=" + Date.now() + HASH }, sid);
  await Promise.race([loaded, sleep(25000)]);
  await sleep(WAIT);

  if (CLICK) {
    const r = await cdp.send("Runtime.evaluate", {
      expression: `(() => { const el = document.querySelector(${JSON.stringify(CLICK)});
        if (!el) return "no match"; el.click(); return "clicked"; })()`, returnByValue: true,
    }, sid);
    console.log("[eval] click", CLICK, "->", r.result && r.result.value);
    await sleep(700);
  }
  const r = await cdp.send("Runtime.evaluate", {
    expression: EXPR, returnByValue: true, awaitPromise: true,
  }, sid);
  if (r.exceptionDetails) console.log("[eval] EXCEPTION:", JSON.stringify(r.exceptionDetails).slice(0, 500));
  console.log(typeof r.result.value === "string" ? r.result.value : JSON.stringify(r.result.value, null, 2));
  await cdp.close();
} finally {
  try { child.kill(); } catch {}
  await sleep(400);
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
}
