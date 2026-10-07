#!/usr/bin/env node
/**
 * tools/ui-audit/probe.mjs
 *
 * Diagnostic companion to audit.mjs: deep-dive ONE css selector at ONE viewport
 * in the real headless Chrome, and print the raw geometry that justifies an
 * audit verdict - bounding box, computed wrap/overflow styles, per-line text
 * boxes (Range.getClientRects) and the ancestor chain with each ancestor's
 * width / overflow-x / scrollWidth-vs-clientWidth.
 *
 * Example (confirming why a button's label wraps to 5 lines at 375px):
 *   node tools/ui-audit/probe.mjs --url http://127.0.0.1:8011 \
 *        --selector "#compareRunBtn" --viewport 375x812
 *
 * Node builtins only.
 */

import http from "node:http";
import net from "node:net";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { Cdp, httpJson, findFreePort, sleep, pad } from "./audit.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");

function parseArgs(argv) {
  const o = {
    url: "http://127.0.0.1:8011",
    selector: null,
    viewport: { width: 375, height: 812 },
    route: "research",
    settleMs: 2500,
    user: process.env.ADMIN_USER || "",
    pass: process.env.ADMIN_PASS || "",
    chrome: process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    showRequests: false,
    json: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const v = () => argv[++i];
    if (a === "--url") o.url = v();
    else if (a === "--selector" || a === "-s") o.selector = v();
    else if (a === "--viewport") {
      const m = v().match(/^(\d+)\s*[xX]\s*(\d+)$/);
      if (!m) throw new Error("--viewport expects WxH");
      o.viewport = { width: Number(m[1]), height: Number(m[2]) };
    } else if (a === "--route") o.route = v().replace(/^#/, "");
    else if (a === "--settle") o.settleMs = Number(v());
    else if (a === "--user") o.user = v();
    else if (a === "--pass") o.pass = v();
    else if (a === "--chrome") o.chrome = v();
    else if (a === "--requests") o.showRequests = true;
    else if (a === "--json") o.json = true;
    else if (a === "--help" || a === "-h") o.help = true;
    else throw new Error("unknown argument: " + a);
  }
  return o;
}

/** Evaluated inside the page. Self-contained. */
function probe(selector) {
  function clean(s, n) {
    if (s === null || s === undefined) return "";
    return String(s).replace(/\s+/g, " ").trim().slice(0, n);
  }
  function pathOf(el) {
    const parts = [];
    let cur = el;
    let guard = 0;
    while (cur && cur.nodeType === 1 && guard++ < 8) {
      let tag = cur.tagName.toLowerCase();
      if (cur.id) { parts.unshift(tag + "#" + cur.id); break; }
      const c = (typeof cur.className === "string" ? cur.className : "").trim().split(/\s+/).filter(Boolean).slice(0, 2).join(".");
      if (c) tag += "." + c;
      parts.unshift(tag);
      cur = cur.parentElement;
    }
    return parts.join(" > ");
  }
  function rectOf(r) {
    return {
      x: Math.round(r.left * 10) / 10, y: Math.round(r.top * 10) / 10,
      width: Math.round(r.width * 10) / 10, height: Math.round(r.height * 10) / 10,
      right: Math.round(r.right * 10) / 10, bottom: Math.round(r.bottom * 10) / 10,
    };
  }
  const out = {
    url: location.href,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    docScrollWidth: document.documentElement.scrollWidth,
    docClientWidth: document.documentElement.clientWidth,
    selector,
    matchCount: 0,
    matches: [],
  };
  const els = Array.from(document.querySelectorAll(selector));
  out.matchCount = els.length;
  for (const el of els.slice(0, 5)) {
    const cs = getComputedStyle(el);
    const m = {
      path: pathOf(el),
      tag: el.tagName.toLowerCase(),
      id: el.id || "",
      className: clean(el.className, 120),
      rect: rectOf(el.getBoundingClientRect()),
      clientWidth: el.clientWidth,
      clientHeight: el.clientHeight,
      scrollWidth: el.scrollWidth,
      scrollHeight: el.scrollHeight,
      offsetWidth: el.offsetWidth,
      computed: {
        display: cs.display, width: cs.width, maxWidth: cs.maxWidth, minWidth: cs.minWidth,
        flex: cs.flex, gridTemplateColumns: cs.gridTemplateColumns,
        whiteSpace: cs.whiteSpace, wordBreak: cs.wordBreak, overflowWrap: cs.overflowWrap,
        overflowX: cs.overflowX, textOverflow: cs.textOverflow, writingMode: cs.writingMode,
        position: cs.position, fontSize: cs.fontSize, lineHeight: cs.lineHeight, padding: cs.padding,
      },
      text: clean(el.textContent, 120),
      textLines: [],
      brokenWords: [],
      ancestors: [],
    };
    // Render each text node word-by-word and record how many visual lines each word spans.
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    let node;
    let lineRects = [];
    while ((node = walker.nextNode())) {
      const raw = node.nodeValue;
      if (!raw || !/\S/.test(raw)) continue;
      const re = /\S+/g;
      let mm;
      while ((mm = re.exec(raw))) {
        const word = mm[0];
        const range = document.createRange();
        range.setStart(node, mm.index);
        range.setEnd(node, mm.index + word.length);
        const rects = Array.from(range.getClientRects()).filter((r) => r.width > 0.5);
        const tops = [];
        for (const r of rects) if (!tops.some((t) => Math.abs(t - r.top) <= 1)) tops.push(r.top);
        if (word.length >= 3) {
          m.brokenWords.push({ word: word.slice(0, 40), visualLines: tops.length, rects: rects.length });
          for (const r of rects) lineRects.push(rectOf(r));
        }
      }
    }
    lineRects.sort((a, b) => (a.y - b.y) || (a.x - b.x));
    m.textLines = lineRects.slice(0, 30);
    let cur = el.parentElement;
    while (cur && cur.nodeType === 1) {
      const ccs = getComputedStyle(cur);
      m.ancestors.push({
        path: pathOf(cur),
        width: Math.round(cur.getBoundingClientRect().width * 10) / 10,
        clientWidth: cur.clientWidth,
        scrollWidth: cur.scrollWidth,
        overflowX: ccs.overflowX,
        display: ccs.display,
      });
      cur = cur.parentElement;
    }
    out.matches.push(m);
  }
  return JSON.stringify(out);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.selector) {
    console.log(`Usage: node tools/ui-audit/probe.mjs --selector <css> [options]

  --url <url>        default http://127.0.0.1:8011
  --selector <css>   required, e.g. "#compareRunBtn" or "nav#navRail"
  --viewport <WxH>   default 375x812
  --route <hash>     default research
  --settle <ms>      default 2500
  --requests         also list network requests observed during the settle window
  --json             print raw JSON only
  --user/--pass      optional HTTP Basic credentials, sent only when both given`);
    return 0;
  }
  /* No login gate: send an Authorization header only if both halves are set. */
  const authHeader = args.user && args.pass
    ? "Basic " + Buffer.from(`${args.user}:${args.pass}`, "utf8").toString("base64")
    : null;
  const withAuth = (headers = {}) => (authHeader ? { ...headers, Authorization: authHeader } : headers);
  const base = args.url.replace(/\/+$/, "");
  const pre = await httpJson(base + "/", { headers: withAuth(), timeoutMs: 8000 });
  if (pre.statusCode === 401) {
    throw new Error(`${base}/ -> HTTP 401: target still requires HTTP Basic auth ` +
      `(set both ADMIN_USER/ADMIN_PASS or --user/--pass); this repo's terminal_api.py has no login gate`);
  }
  if (pre.statusCode !== 200) throw new Error(`${base}/ -> HTTP ${pre.statusCode}`);

  const debugPort = await findFreePort();
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "nse-ui-probe-"));
  const child = spawn(args.chrome, [
    "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
    "--no-first-run", "--no-default-browser-check", "--disable-extensions",
    "--remote-allow-origins=*", `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profileDir}`, "about:blank",
  ], { stdio: "ignore", windowsHide: true });

  let cdp = null;
  try {
    const version = await (async () => {
      const t0 = Date.now();
      while (Date.now() - t0 < 25000) {
        try {
          const r = await httpJson(`http://127.0.0.1:${debugPort}/json/version`, { timeoutMs: 2000 });
          if (r.statusCode === 200) return JSON.parse(r.body);
        } catch { /* retry */ }
        await sleep(250);
      }
      throw new Error("Chrome DevTools endpoint never came up on :" + debugPort);
    })();
    cdp = await Cdp.connect(version.webSocketDebuggerUrl, 15000);
    const t = await cdp.send("Target.createTarget", { url: "about:blank" });
    const a = await cdp.send("Target.attachToTarget", { targetId: t.targetId, flatten: true });
    const sid = a.sessionId;
    await cdp.send("Page.enable", {}, sid);
    await cdp.send("Runtime.enable", {}, sid);
    await cdp.send("Network.enable", {}, sid);
    if (authHeader) {
      await cdp.send("Network.setExtraHTTPHeaders", { headers: withAuth() }, sid);
    }
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: args.viewport.width, height: args.viewport.height, deviceScaleFactor: 1,
      mobile: args.viewport.width < 768, screenWidth: args.viewport.width, screenHeight: args.viewport.height,
    }, sid);

    const urls = [];
    if (args.showRequests) {
      const orig = cdp._onMessage.bind(cdp);
      cdp._onMessage = (ev) => {
        orig(ev);
        try {
          const msg = JSON.parse(typeof ev.data === "string" ? ev.data : "{}");
          if (msg.method === "Network.requestWillBeSent") urls.push(msg.params.request.url);
        } catch { /* ignore */ }
      };
    }

    const u = new URL(base + "/");
    u.searchParams.set("_probe", String(Date.now()));
    u.hash = args.route ? "#" + args.route : "";
    const load = cdp.once("Page.loadEventFired", sid, 30000).then(() => true).catch(() => false);
    await cdp.send("Page.navigate", { url: u.toString() }, sid);
    const loaded = await load;
    await sleep(args.settleMs);
    const res = await cdp.send("Runtime.evaluate", {
      expression: `(${probe.toString()})(${JSON.stringify(args.selector)})`,
      returnByValue: true,
    }, sid, 30000);
    const data = typeof res.result.value === "string" ? JSON.parse(res.result.value) : res.result.value;
    data.loadEventFired = loaded;

    if (args.json) {
      if (args.showRequests) data.observedRequests = urls;
      console.log(JSON.stringify(data, null, 2));
    } else {
      console.log(`\nprobe ${args.selector} @ ${args.viewport.width}x${args.viewport.height} ${data.url}`);
      console.log(`viewport=${data.viewportWidth} doc=${data.docClientWidth}/${data.docScrollWidth} matches=${data.matchCount} loadEventFired=${loaded}`);
      for (const m of data.matches) {
        console.log(`\n  ${m.path}`);
        console.log(`    rect       x=${m.rect.x} y=${m.rect.y} w=${m.rect.width} h=${m.rect.height} right=${m.rect.right}`);
        console.log(`    client     ${m.clientWidth}x${m.clientHeight}   scroll ${m.scrollWidth}x${m.scrollHeight}`);
        console.log(`    display=${m.computed.display} width=${m.computed.width} flex=${m.computed.flex}`);
        console.log(`    wrap       white-space=${m.computed.whiteSpace} word-break=${m.computed.wordBreak} overflow-wrap=${m.computed.overflowWrap}`);
        console.log(`    text       "${m.text}"`);
        const broken = m.brokenWords.filter((w) => w.visualLines > 1);
        if (broken.length) {
          console.log(`    BROKEN WORDS (${broken.length}):`);
          for (const w of broken.slice(0, 8)) console.log(`      "${w.word}" spans ${w.visualLines} visual lines (${w.rects} rects)`);
        } else {
          console.log("    BROKEN WORDS: none");
        }
        if (m.textLines.length) {
          console.log(`    line boxes (first ${Math.min(5, m.textLines.length)}):`);
          for (const r of m.textLines.slice(0, 5)) console.log(`      y=${r.y} x=${r.x} w=${r.width} h=${r.height}`);
        }
        console.log("    ancestors (closest first):");
        for (const an of m.ancestors.slice(0, 6)) {
          console.log(`      ${pad(an.path.slice(-52), 54)} w=${pad(an.width, 8)} client=${pad(an.clientWidth, 6)} scroll=${pad(an.scrollWidth, 7)} overflow-x=${an.overflowX}`);
        }
      }
      if (args.showRequests) {
        console.log(`\n  network requests observed (${urls.length}):`);
        for (const s of urls.slice(0, 40)) console.log("    " + s);
      }
    }
    return 0;
  } finally {
    try { if (cdp && cdp.isOpen) await cdp.send("Browser.close", {}, undefined, 4000); } catch { /* ignore */ }
    try { cdp?.close(); } catch { /* ignore */ }
    await sleep(400);
    if (child.exitCode === null) {
      try { child.kill(); } catch { /* ignore */ }
      await sleep(800);
      if (child.exitCode === null && process.platform === "win32") {
        try { spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true }); } catch { /* ignore */ }
      }
    }
    try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch { /* ignore */ }
  }
}

process.exit(await main().catch((err) => {
  console.error("[probe] FATAL " + (err.stack || err.message));
  return 2;
}));
