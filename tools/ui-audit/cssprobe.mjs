#!/usr/bin/env node
/**
 * tools/ui-audit/cssprobe.mjs
 * Print every CSS rule that matches a selector, with the winning declaration
 * for a given property. Diagnoses "why is this box the wrong size".
 *
 *   node tools/ui-audit/cssprobe.mjs --selector ".fx-search" --props height,padding,display
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Cdp, httpJson, findFreePort, sleep } from "./audit.mjs";

const args = process.argv.slice(2);
function arg(name, dflt) {
  const i = args.indexOf("--" + name);
  return i >= 0 ? args[i + 1] : dflt;
}
const URL_ = arg("url", "http://127.0.0.1:8011");
const SELECTOR = arg("selector", ".fx-search");
const PROPS = arg("props", "display,height,min-height,padding,width,flex,align-items,box-sizing").split(",");
const VIEWPORT = arg("viewport", "375x812").split("x").map(Number);
const CHROME = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "cssprobe-"));
const port = await findFreePort();
const child = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--hide-scrollbars", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "about:blank",
], { stdio: "ignore" });

async function version() {
  for (let i = 0; i < 60; i++) {
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
  const target = await cdp.send("Target.createTarget", { url: "about:blank" });
  const attached = await cdp.send("Target.attachToTarget", { targetId: target.targetId, flatten: true });
  const sid = attached.sessionId;
  cdp.sessionId = sid;
  await cdp.send("Page.enable", {}, sid);
  await cdp.send("Runtime.enable", {}, sid);
  await cdp.send("Network.enable", {}, sid);
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true }, sid);
  /* No login gate: an Authorization header is sent only when both halves of an
     explicit credential pair are present in ADMIN_USER / ADMIN_PASS. */
  const user = process.env.ADMIN_USER || "";
  const pass = process.env.ADMIN_PASS || "";
  if (user && pass) {
    await cdp.send("Network.setExtraHTTPHeaders", {
      headers: { Authorization: "Basic " + Buffer.from(`${user}:${pass}`).toString("base64") },
    }, sid);
  }
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: VIEWPORT[0], height: VIEWPORT[1], deviceScaleFactor: 1, mobile: VIEWPORT[0] < 768,
  }, sid);
  const loaded = new Promise((res) => {
    const off = cdp.on("Page.loadEventFired", () => { off(); res(); });
  });
  await cdp.send("Page.navigate", { url: URL_.replace(/#.*$/, "") + "/?_cssprobe=1#research" }, sid);
  await Promise.race([loaded, sleep(20000)]);
  await sleep(1500);

  const expr = `(() => {
    const el = document.querySelector(${JSON.stringify(SELECTOR)});
    if (!el) return { error: "no match for " + ${JSON.stringify(SELECTOR)} };
    const cs = getComputedStyle(el);
    const props = ${JSON.stringify(PROPS)};
    const computed = {};
    props.forEach(p => { computed[p] = cs.getPropertyValue(p); });
    // walk every stylesheet rule that matches, in document order
    const rules = [];
    for (const sheet of Array.from(document.styleSheets)) {
      let list;
      try { list = sheet.cssRules; } catch (e) { continue; }
      const walk = (ruleList, media) => {
        for (const rule of Array.from(ruleList)) {
          if (rule.cssRules && rule.conditionText !== undefined) { walk(rule.cssRules, rule.conditionText); continue; }
          if (!rule.selectorText) continue;
          let matches = false;
          try { matches = el.matches(rule.selectorText); } catch (e) { matches = false; }
          if (!matches) continue;
          const decls = [];
          for (const p of props) {
            const v = rule.style.getPropertyValue(p);
            if (v) decls.push(p + ": " + v + (rule.style.getPropertyPriority(p) ? " !important" : ""));
          }
          if (decls.length) rules.push({
            sheet: (sheet.href || "inline").split("/").pop(),
            media: media || "",
            selector: rule.selectorText,
            decls,
          });
        }
      };
      walk(list, "");
    }
    const r = el.getBoundingClientRect();
    return {
      tag: el.tagName, cls: el.className, rect: { w: Math.round(r.width), h: Math.round(r.height) },
      computed, rules,
    };
  })()`;

  const res = await cdp.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, sid);
  const out = res.result && res.result.value;
  if (out && out.error) {
    const dbg = await cdp.send("Runtime.evaluate", {
      expression: `JSON.stringify({ url: location.href, title: document.title, len: document.documentElement.outerHTML.length, body: document.body ? document.body.firstElementChild?.tagName : null })`,
      returnByValue: true,
    }, sid);
    console.log("DEBUG:", dbg.result && dbg.result.value);
  }
  console.log(JSON.stringify(out, null, 2));
  await cdp.close();
} finally {
  try { child.kill(); } catch {}
  await sleep(400);
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
}
