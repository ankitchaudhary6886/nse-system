#!/usr/bin/env node
/**
 * tools/ui-audit/audit.mjs
 *
 * Dependency-free headless-Chrome mobile-layout audit for the NSE Research
 * terminal. Drives real Chrome over the DevTools Protocol using only Node
 * builtins + the Node 22+ global WebSocket. No npm packages required.
 *
 * What it does, per viewport x route:
 *   1. Emulation.setDeviceMetricsOverride(width, height, dsf=1, mobile)
 *   2. Page.navigate -> wait Page.loadEventFired -> wait for network idle
 *   3. Runtime.evaluate of pageMeasure()  => real getBoundingClientRect geometry:
 *      document scrollWidth/clientWidth, horizontal overflow, ranked offenders,
 *      and Range.getClientRects()-based single-word line-break detection.
 *   4. Page.getLayoutMetrics (independent CDP-provided cross-check)
 *   5. Page.captureScreenshot(captureBeyondViewport:true) -> out/<w>x<h>-<route>.png
 *   6. Appends the measurement to out/report.json
 *
 * Usage:
 *   node tools/ui-audit/audit.mjs --url http://127.0.0.1:8011
 *   node tools/ui-audit/audit.mjs                       # defaults to :8011
 *   node tools/ui-audit/audit.mjs --spawn-server        # starts uvicorn itself
 *
 * Exit codes: 0 = PASS, 1 = mobile horizontal overflow detected, 2 = harness error.
 */

import http from "node:http";
import net from "node:net";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const OUT_DIR = path.join(__dirname, "out");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);
const warn = (...a) => console.error(...a);

/* ===================================================================== */
/* CLI                                                                   */
/* ===================================================================== */

function parseArgs(argv) {
  const o = {
    url: "http://127.0.0.1:8011",
    routes: ["research"],
    viewports: [
      { width: 375, height: 812 },
      { width: 390, height: 844 },
      { width: 768, height: 1024 },
      { width: 1440, height: 900 },
    ],
    settleMs: 2500,
    idleMs: 700,
    loadTimeoutMs: 30000,
    navTimeoutMs: 45000,
    user: process.env.ADMIN_USER || "",
    pass: process.env.ADMIN_PASS || "",
    chrome:
      process.env.CHROME_PATH ||
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    outDir: OUT_DIR,
    failWidths: [375, 390],
    failOnTextOverflow: false,
    spawnServer: false,
    serverPort: 8011,
    blockExternal: false,
    keepProfile: false,
    headful: false,
    verbose: false,
    maxOffenders: 25,
    maxWordChecks: 2500,
    help: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const val = () => argv[++i];
    if (a === "--url") o.url = val();
    else if (a === "--routes") o.routes = val().split(",").map((s) => s.trim().replace(/^#/, "")).filter(Boolean);
    else if (a === "--viewports")
      o.viewports = val()
        .split(",")
        .map((s) => {
          const m = s.trim().match(/^(\d+)\s*[xX]\s*(\d+)$/);
          if (!m) throw new Error("bad --viewports entry: " + s + " (expected WxH)");
          return { width: Number(m[1]), height: Number(m[2]) };
        });
    else if (a === "--settle") o.settleMs = Number(val());
    else if (a === "--idle") o.idleMs = Number(val());
    else if (a === "--fail-widths") o.failWidths = val().split(",").map(Number);
    else if (a === "--fail-on-text-overflow") o.failOnTextOverflow = true;
    else if (a === "--out") o.outDir = path.resolve(val());
    else if (a === "--user") o.user = val();
    else if (a === "--pass") o.pass = val();
    else if (a === "--chrome") o.chrome = val();
    else if (a === "--spawn-server") o.spawnServer = true;
    else if (a === "--server-port") o.serverPort = Number(val());
    else if (a === "--block-external") o.blockExternal = true;
    else if (a === "--keep-profile") o.keepProfile = true;
    else if (a === "--headful") o.headful = true;
    else if (a === "--verbose" || a === "-v") o.verbose = true;
    else if (a === "--max-word-checks") o.maxWordChecks = Number(val());
    else if (a === "--help" || a === "-h") o.help = true;
    else throw new Error("unknown argument: " + a);
  }
  return o;
}

const HELP = `node tools/ui-audit/audit.mjs [options]

  --url <url>            target base url (default http://127.0.0.1:8011)
  --routes <a,b>         hash routes, '#' optional (default research)
  --viewports <WxH,...>  default 375x812,390x844,768x1024,1440x900
  --settle <ms>          extra settle wait after network idle (default 2500)
  --idle <ms>            network-idle window (default 700)
  --fail-widths <a,b>    viewport widths that fail the run (default 375,390)
  --fail-on-text-overflow  also fail the run when a label paints outside its own
                         box at a gated width (strict mode; default off)
  --out <dir>            output dir (default tools/ui-audit/out)
  --user/--pass          optional HTTP Basic credentials; an Authorization
                         header is sent ONLY when both are given (via
                         ADMIN_USER/ADMIN_PASS env vars or both flags).
                         The app is unauthenticated by default, so the normal
                         path sends no credentials at all.
  --chrome <path>        chrome.exe path
  --spawn-server         start uvicorn via serve.mjs and shut it down afterwards
  --server-port <n>      port for --spawn-server (default 8011, auto-picks if busy)
  --block-external       block third-party hosts (unpkg etc) for offline runs
  --keep-profile         keep the temp Chrome profile (debugging)
  --headful              run a visible Chrome instead of --headless=new
  --max-word-checks <n>  cap on per-word Range.getClientRects checks (default 2500)
  -v, --verbose          log every CDP step
`;

/* ===================================================================== */
/* The in-page measurement expression (stringified + evaluated via CDP)  */
/* Runs inside Chrome. Must be fully self-contained: no closure captures. */
/* ===================================================================== */

function pageMeasure(opts) {
  var out = {
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    title: document.title,
    readyState: document.readyState,
    url: location.href,
    hash: location.hash,
    bodyChildCount: document.body ? document.body.children.length : 0,
    bodyTextLength: 0,
    appMarkers: { navRail: false, main: false, viewResearch: false },
    docScrollWidth: 0,
    docClientWidth: 0,
    horizontalOverflowPx: 0,
    offenders: [],
    offenderCount: 0,
    pageLevelOffenderCount: 0,
    offendersInsideScrollContainer: 0,
    textNodesWrappingBadly: null,
    badWrapChecked: 0,
    badWrapError: null,
    textOverflowingOwnBox: [],
    textOverflowError: null,
    notes: [],
  };
  try {
    var cfg = opts || {};
    var maxOffenders = cfg.maxOffenders || 25;
    var maxWordChecks = cfg.maxWordChecks || 2500;
    var vw = window.innerWidth;
    var dev = document.documentElement;

    function clean(s, n) {
      if (s === null || s === undefined) return "";
      return String(s).replace(/\s+/g, " ").trim().slice(0, n);
    }
    function clsOf(el) {
      if (!el.className || typeof el.className !== "string") return "";
      return clean(el.className, 80);
    }
    function cssPath(el) {
      var parts = [];
      var cur = el;
      var guard = 0;
      while (cur && cur.nodeType === 1 && guard < 7) {
        guard++;
        var tag = cur.tagName.toLowerCase();
        if (cur.id) {
          parts.unshift(tag + "#" + cur.id);
          break;
        }
        var c = clsOf(cur).split(" ").filter(Boolean).slice(0, 2).join(".");
        if (c) tag += "." + c;
        var parent = cur.parentElement;
        if (parent) {
          var same = [];
          for (var i = 0; i < parent.children.length; i++) {
            if (parent.children[i].tagName === cur.tagName) same.push(parent.children[i]);
          }
          if (same.length > 1) tag += ":nth-of-type(" + (same.indexOf(cur) + 1) + ")";
        }
        parts.unshift(tag);
        cur = cur.parentElement;
      }
      return parts.join(" > ");
    }
    function clipperAncestor(el) {
      var cur = el.parentElement;
      while (cur && cur.nodeType === 1) {
        var cs = getComputedStyle(cur);
        var ox = cs.overflowX;
        if (ox === "auto" || ox === "scroll" || ox === "hidden" || ox === "clip") return cur;
        cur = cur.parentElement;
      }
      return null;
    }

    var bodySW = document.body ? document.body.scrollWidth : 0;
    out.docScrollWidth = Math.max(dev.scrollWidth, bodySW);
    out.docClientWidth = dev.clientWidth;
    out.horizontalOverflowPx = Math.max(0, out.docScrollWidth - out.docClientWidth);
    out.bodyTextLength = document.body
      ? document.body.innerText.replace(/\s+/g, " ").trim().length
      : 0;
    out.appMarkers = {
      navRail: !!document.querySelector("nav#navRail"),
      main: !!document.querySelector("main"),
      viewResearch: !!document.querySelector("#view-research"),
    };

    var SKIP = {
      SCRIPT: 1, STYLE: 1, LINK: 1, META: 1, HEAD: 1, TITLE: 1,
      NOSCRIPT: 1, TEMPLATE: 1, BR: 1, BASE: 1, PARAM: 1,
    };
    var all = document.querySelectorAll("*");
    var offenders = [];
    for (var n = 0; n < all.length; n++) {
      var el = all[n];
      if (SKIP[el.tagName]) continue;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0") continue;
      var r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;

      var overRight = r.right - vw;
      var sw = el.scrollWidth;
      var cw = el.clientWidth;
      var selfOverflow = 0;
      // "not a scroll container" per the audit spec: only overflow-x:visible
      // boxes whose content is wider than their own client box count here.
      if (cw > 0 && sw > cw + 1 && cs.overflowX === "visible") selfOverflow = sw - cw;

      var reason = null;
      if (overRight > 1) reason = "rect-right";
      else if (selfOverflow > 0) reason = "scroll-width";
      if (!reason) continue;

      // An element whose ancestor clips or scrolls it is not, on its own,
      // evidence of page-level overflow. Keep it, but flag + rank it lower.
      var inScroll = false;
      var clipEl = clipperAncestor(el);
      if (clipEl) {
        var ccs = getComputedStyle(clipEl);
        var cr = clipEl.getBoundingClientRect();
        var scrollable = ccs.overflowX === "auto" || ccs.overflowX === "scroll";
        var withinViewport = cr.right <= vw + 1;
        inScroll = scrollable || withinViewport;
      }

      var overflowPx = reason === "rect-right" ? overRight : selfOverflow;
      offenders.push({
        tag: el.tagName.toLowerCase(),
        id: el.id || "",
        className: clsOf(el),
        reason: reason,
        overflowPx: Math.round(overflowPx * 10) / 10,
        right: Math.round(r.right * 10) / 10,
        left: Math.round(r.left * 10) / 10,
        width: Math.round(r.width * 10) / 10,
        scrollWidth: sw,
        clientWidth: cw,
        overflowXComputed: cs.overflowX,
        position: cs.position,
        inScrollContainer: inScroll,
        text: clean(el.textContent, 60),
        path: cssPath(el),
      });
    }
    // Unclipped page-level offenders first, then worst overflow first.
    offenders.sort(function (a, b) {
      if (a.inScrollContainer !== b.inScrollContainer) return a.inScrollContainer ? 1 : -1;
      return b.overflowPx - a.overflowPx;
    });
    out.offenderCount = offenders.length;
    var inScrollCount = 0;
    var pageLevelCount = 0;
    for (var q = 0; q < offenders.length; q++) {
      if (offenders[q].inScrollContainer) inScrollCount++;
      else pageLevelCount++;
    }
    out.offendersInsideScrollContainer = inScrollCount;
    out.pageLevelOffenderCount = pageLevelCount;
    out.offenders = offenders.slice(0, maxOffenders);

    // ---- single-word line-break detection (real, via Range.getClientRects) ----
    var badWrap = [];
    var checks = 0;
    var badWrapError = null;
    try {
      var root = document.body || dev;
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      var node;
      while ((node = walker.nextNode())) {
        if (badWrap.length >= 20 || checks >= maxWordChecks) break;
        var raw = node.nodeValue;
        if (!raw || !/\S/.test(raw)) continue;
        var parentEl = node.parentElement;
        if (!parentEl) continue;
        var pcs = getComputedStyle(parentEl);
        if (pcs.display === "none" || pcs.visibility === "hidden") continue;
        var pr = parentEl.getBoundingClientRect();
        if (pr.width === 0 || pr.height === 0) continue;
        var re = /\S+/g;
        var m;
        while ((m = re.exec(raw))) {
          if (checks >= maxWordChecks) break;
          var word = m[0];
          if (word.length < 4) continue;
          var range = document.createRange();
          range.setStart(node, m.index);
          range.setEnd(node, m.index + word.length);
          var rects = range.getClientRects();
          var lines = 0;
          var lastTop = null;
          for (var k = 0; k < rects.length; k++) {
            var rc = rects[k];
            if (rc.width <= 0.5) continue;
            if (lastTop === null || Math.abs(rc.top - lastTop) > 1) {
              lines++;
              lastTop = rc.top;
            }
          }
          checks++;
          if (lines > 1) {
            var cause = "unbreakable-token";
            if (pcs.wordBreak === "break-all") cause = "word-break:break-all";
            else if (pcs.overflowWrap === "anywhere") cause = "overflow-wrap:anywhere";
            badWrap.push({
              tag: parentEl.tagName.toLowerCase(),
              id: parentEl.id || "",
              className: clsOf(parentEl),
              word: word.slice(0, 40),
              lines: lines,
              cause: cause,
              path: cssPath(parentEl),
            });
            break; // one report per text node is enough
          }
        }
      }
      out.textNodesWrappingBadly = badWrap;
    } catch (e) {
      out.textNodesWrappingBadly = null;
      badWrapError = String((e && e.message) || e);
    }
    out.badWrapChecked = checks;
    out.badWrapError = badWrapError;
    if (checks >= maxWordChecks) out.notes.push("word-check cap reached (" + maxWordChecks + ")");

    // ---- text painted outside its own box (squeezed nowrap labels collide) ----
    // Compares an element's own text line-boxes (Range.getClientRects over its
    // direct text nodes) against its border box. Catches flex-shrunk labels with
    // white-space:nowrap that overlap the next sibling - a breakage that causes
    // no document-level horizontal overflow and is therefore invisible to the
    // scrollWidth gate above.
    var textOut = [];
    var textOutError = null;
    try {
      var cands = document.querySelectorAll("*");
      for (var ti = 0; ti < cands.length && textOut.length < 20; ti++) {
        var tel = cands[ti];
        if (SKIP[tel.tagName]) continue;
        if (tel.namespaceURI && tel.namespaceURI !== "http://www.w3.org/1999/xhtml") continue;
        var tcs = getComputedStyle(tel);
        if (tcs.display === "none" || tcs.visibility === "hidden" || tcs.opacity === "0") continue;
        if (tcs.textOverflow === "ellipsis") continue; // intentional truncation
        var direct = "";
        var cj;
        for (cj = 0; cj < tel.childNodes.length; cj++) {
          var cn = tel.childNodes[cj];
          if (cn.nodeType === 3 && cn.nodeValue && /\S/.test(cn.nodeValue)) { direct = cn.nodeValue; break; }
        }
        if (!direct) continue;
        var tr = tel.getBoundingClientRect();
        if (tr.width === 0 || tr.height === 0) continue;
        var minL = Infinity;
        var maxR = -Infinity;
        var rr = document.createRange();
        for (cj = 0; cj < tel.childNodes.length; cj++) {
          var tn = tel.childNodes[cj];
          if (tn.nodeType !== 3 || !tn.nodeValue || !/\S/.test(tn.nodeValue)) continue;
          rr.setStart(tn, 0);
          rr.setEnd(tn, tn.nodeValue.length);
          var trs = rr.getClientRects();
          for (var ri = 0; ri < trs.length; ri++) {
            var trc = trs[ri];
            if (trc.width <= 0.5) continue;
            if (trc.left < minL) minL = trc.left;
            if (trc.right > maxR) maxR = trc.right;
          }
        }
        if (maxR === -Infinity) continue;
        var worst = Math.max(maxR - tr.right, tr.left - minL);
        if (worst <= 1) continue;
        var ancClipped = false;
        var anc = tel.parentElement;
        while (anc && anc.nodeType === 1) {
          var acs = getComputedStyle(anc);
          if (acs.overflowX === "hidden" || acs.overflowX === "clip") { ancClipped = true; break; }
          anc = anc.parentElement;
        }
        textOut.push({
          tag: tel.tagName.toLowerCase(),
          id: tel.id || "",
          className: clsOf(tel),
          text: clean(direct, 60),
          overflowPx: Math.round(worst * 10) / 10,
          boxWidth: Math.round(tr.width * 10) / 10,
          boxRight: Math.round(tr.right * 10) / 10,
          textRight: Math.round(maxR * 10) / 10,
          whiteSpace: tcs.whiteSpace,
          flexShrink: tcs.flexShrink,
          ancestorClipped: ancClipped,
          path: cssPath(tel),
        });
      }
      textOut.sort(function (a, b) {
        if (a.ancestorClipped !== b.ancestorClipped) return a.ancestorClipped ? 1 : -1;
        return b.overflowPx - a.overflowPx;
      });
      out.textOverflowingOwnBox = textOut;
    } catch (e) {
      out.textOverflowingOwnBox = null;
      textOutError = String((e && e.message) || e);
    }
    out.textOverflowError = textOutError;

    return JSON.stringify(out);
  } catch (e) {
    return JSON.stringify({
      error: String((e && e.message) || e),
      stack: String((e && e.stack) || "").slice(0, 400),
      viewportWidth: window.innerWidth,
    });
  }
}

/* ===================================================================== */
/* CDP client over the built-in global WebSocket                         */
/* ===================================================================== */

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this._id = 0;
    this._pending = new Map();
    this._handlers = new Map(); // method -> [{sessionId|null, resolve, reject, timer}]
    this._closed = false;
    this.sessionId = null;
  }

  static connect(wsUrl, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      let ws;
      try {
        ws = new WebSocket(wsUrl);
      } catch (err) {
        reject(new Error("WebSocket ctor failed for " + wsUrl + ": " + err.message));
        return;
      }
      const cdp = new Cdp(ws);
      const timer = setTimeout(() => {
        try { ws.close(); } catch { /* ignore */ }
        reject(new Error("CDP websocket connect timeout after " + timeoutMs + "ms: " + wsUrl));
      }, timeoutMs);
      ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve(cdp);
      });
      ws.addEventListener("error", (ev) => {
        clearTimeout(timer);
        reject(new Error("CDP websocket error on " + wsUrl + ": " + ((ev && (ev.message || ev.type)) || "unknown")));
      });
      ws.addEventListener("message", (ev) => cdp._onMessage(ev));
      ws.addEventListener("close", () => cdp._onClose());
    });
  }

  get isOpen() {
    return !this._closed && this.ws.readyState === 1;
  }

  close() {
    this._closed = true;
    try { this.ws.close(); } catch { /* ignore */ }
  }

  _onMessage(ev) {
    let msg;
    const data = ev.data;
    try {
      msg = JSON.parse(typeof data === "string" ? data : Buffer.from(data).toString("utf8"));
    } catch (err) {
      warn("[cdp] unparseable frame: " + err.message);
      return;
    }
    if (msg.id !== undefined && msg.id !== null) {
      const p = this._pending.get(msg.id);
      if (!p) return;
      this._pending.delete(msg.id);
      clearTimeout(p.timer);
      if (msg.error) {
        const e = new Error(msg.method + " failed: " + (msg.error.message || JSON.stringify(msg.error)));
        e.cdpError = msg.error;
        p.reject(e);
      } else {
        p.resolve(msg.result || {});
      }
      return;
    }
    if (msg.method) {
      const list = this._handlers.get(msg.method);
      if (!list || !list.length) return;
      for (let i = 0; i < list.length; i++) {
        const h = list[i];
        if (h.sessionId && msg.sessionId && h.sessionId !== msg.sessionId) continue;
        this._handlers.get(msg.method).splice(i, 1);
        clearTimeout(h.timer);
        h.resolve(msg.params || {});
        return;
      }
    }
  }

  _onClose() {
    this._closed = true;
    for (const [, p] of this._pending) {
      clearTimeout(p.timer);
      p.reject(new Error("CDP connection closed while awaiting " + p.method));
    }
    this._pending.clear();
    for (const [, list] of this._handlers) {
      for (const h of list) {
        clearTimeout(h.timer);
        h.reject(new Error("CDP connection closed while waiting for event"));
      }
    }
    this._handlers.clear();
  }

  send(method, params = {}, sessionId = undefined, timeoutMs = 45000) {
    if (this._closed) return Promise.reject(new Error("CDP closed; cannot send " + method));
    const id = ++this._id;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._pending.delete(id);
        reject(new Error(method + " timed out after " + timeoutMs + "ms"));
      }, timeoutMs);
      this._pending.set(id, { resolve, reject, method, timer });
      try {
        this.ws.send(JSON.stringify(payload));
      } catch (err) {
        this._pending.delete(id);
        clearTimeout(timer);
        reject(new Error("send failed for " + method + ": " + err.message));
      }
    });
  }

  /** Wait for one CDP event. Rejects on timeout (callers usually .catch). */
  once(method, sessionId = undefined, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
      if (!this._handlers.has(method)) this._handlers.set(method, []);
      const entry = { sessionId, resolve, reject, timer: null };
      entry.timer = setTimeout(() => {
        const list = this._handlers.get(method) || [];
        const i = list.indexOf(entry);
        if (i >= 0) list.splice(i, 1);
        reject(new Error("event " + method + " not received within " + timeoutMs + "ms"));
      }, timeoutMs);
      this._handlers.get(method).push(entry);
    });
  }

  /** Fire-and-forget event tap used for network-idle accounting. */
  on(method, fn) {
    if (!this._handlers.has(method)) this._handlers.set(method, []);
    // Events are normally consumed via once(); a permanent tap lives in these sets.
    if (!this._taps) this._taps = new Map();
    if (!this._taps.has(method)) this._taps.set(method, []);
    this._taps.get(method).push(fn);
  }

  /** Dispatch taps too - called from _onMessage via the wrapper below. */
  _dispatchTaps(method, params) {
    const list = this._taps && this._taps.get(method);
    if (!list) return;
    for (const fn of list) {
      try { fn(params); } catch { /* ignore */ }
    }
  }
}

/* ===================================================================== */
/* helpers                                                               */
/* ===================================================================== */

function httpJson(url, { headers = {}, timeoutMs = 5000 } = {}) {
  return new Promise((resolve, reject) => {
    let req;
    try {
      req = http.get(url, { headers }, (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const body = Buffer.concat(chunks).toString("utf8");
          resolve({ statusCode: res.statusCode, body, headers: res.headers });
        });
      });
    } catch (err) {
      reject(err);
      return;
    }
    req.setTimeout(timeoutMs, () => req.destroy(new Error("timeout " + timeoutMs + "ms: " + url)));
    req.on("error", reject);
  });
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function slugRoute(route) {
  const s = String(route || "root").replace(/^#/, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return s || "root";
}

async function waitForDeadline(fn, { timeoutMs, intervalMs = 150, label = "condition" }) {
  const t0 = Date.now();
  let last = null;
  while (Date.now() - t0 < timeoutMs) {
    try {
      const v = await fn();
      if (v) return v;
    } catch (err) {
      last = err;
    }
    await sleep(intervalMs);
  }
  if (last) throw last;
  throw new Error("timed out waiting for " + label + " (" + timeoutMs + "ms)");
}

function pad(s, n) {
  s = String(s);
  return s.length >= n ? s : s + " ".repeat(n - s.length);
}

function taskkillTree(pid) {
  try {
    const r = spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
    return r.status === 0;
  } catch {
    return false;
  }
}

/* ===================================================================== */
/* main                                                                  */
/* ===================================================================== */

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    log(HELP);
    return 0;
  }
  if (process.platform !== "win32" && args.chrome === "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe") {
    args.chrome = "/usr/bin/google-chrome";
  }

  fs.mkdirSync(args.outDir, { recursive: true });
  /* The terminal has no login gate: credentials are OPTIONAL and only sent
     when the operator explicitly supplies both halves. Default = no header. */
  const authHeader = args.user && args.pass
    ? "Basic " + Buffer.from(`${args.user}:${args.pass}`, "utf8").toString("base64")
    : null;
  const withAuth = (headers = {}) => (authHeader ? { ...headers, Authorization: authHeader } : headers);

  let srvHandle = null;
  let base = args.url.replace(/\/+$/, "");

  if (args.spawnServer) {
    const { startServer } = await import("./serve.mjs");
    log(`[audit] --spawn-server: starting uvicorn on port ${args.serverPort} ...`);
    srvHandle = await startServer({
      port: args.serverPort,
      user: args.user,
      pass: args.pass,
      repoRoot: REPO_ROOT,
      timeoutMs: 45000,
      quiet: false,
    });
    base = srvHandle.url;
    log(`[audit] server ready at ${base}`);
  }

  /* ---- preflight: is the target actually serving the terminal? ---- */
  let pre;
  try {
    pre = await httpJson(base + "/", { headers: withAuth(), timeoutMs: 8000 });
  } catch (err) {
    throw new Error(
      `Cannot reach ${base}/ (${err.message}).\n` +
        `Start the app first:  node tools/ui-audit/serve.mjs\n` +
        `                 or:  .\\env\\Scripts\\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8011`
    );
  }
  if (pre.statusCode === 401) {
    throw new Error(
      `${base}/ -> HTTP 401. The target still enforces HTTP Basic auth; this repo's ` +
        `terminal_api.py has no login gate, so that server is stale. If it really is ` +
        `gated, set both ADMIN_USER / ADMIN_PASS env vars (or pass --user and --pass).`
    );
  }
  if (pre.statusCode !== 200) {
    throw new Error(`${base}/ -> HTTP ${pre.statusCode} (expected 200)`);
  }
  const looksLikeTerminal = /<html[\s>]/i.test(pre.body) && /<title>\s*NSE Research Terminal/i.test(pre.body);
  if (!looksLikeTerminal) {
    warn(`[audit] WARNING: ${base}/ returned 200 but does not look like the NSE terminal index.html`);
  }
  log(`[audit] preflight OK  ${base}/ -> 200 (${pre.body.length} bytes)`);

  /* ---- choose a debug port + temp profile, launch Chrome ---- */
  const debugPort = await findFreePort();
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "nse-ui-audit-"));
  const chromeArgs = [
    args.headful ? "--headless=no" : "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--hide-scrollbars",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-dev-shm-usage",
    "--force-device-scale-factor=1",
    "--mute-audio",
    "--window-size=1440,900",
    "--remote-allow-origins=*",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ];
  chromeArgs.splice(0, 0, "--no-sandbox");

  log(`[audit] launching chrome (debug port ${debugPort})\n        ${args.chrome}`);
  if (!fs.existsSync(args.chrome)) throw new Error("chrome.exe not found at: " + args.chrome);

  let chromeStdioLog = "";
  let child;
  try {
    child = spawn(args.chrome, chromeArgs, { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  } catch (err) {
    // Some confined sandboxes refuse pipes; retry with inherited/ignored stdio.
    warn("[audit] chrome spawn with pipes failed (" + err.message + "); retrying with stdio=ignore");
    child = spawn(args.chrome, chromeArgs, { stdio: "ignore", windowsHide: true });
  }
  child.stdout?.on("data", (d) => { chromeStdioLog += d.toString("utf8"); });
  child.stderr?.on("data", (d) => { chromeStdioLog += d.toString("utf8"); });
  child.on("exit", (code) => { if (args.verbose) log(`[audit] chrome exited code=${code}`); });

  let cdp = null;
  const results = [];
  let mode = "cdp-full-layout";
  let chromeVersion = "unknown";
  let fatal = null;

  const cleanup = async () => {
    try {
      if (cdp && cdp.isOpen) await cdp.send("Browser.close", {}, undefined, 4000);
    } catch { /* ignore */ }
    try { cdp?.close(); } catch { /* ignore */ }
    await sleep(400);
    if (child && child.exitCode === null && child.signalCode === null) {
      try { child.kill(); } catch { /* ignore */ }
      await sleep(900);
      if (child.exitCode === null && process.platform === "win32") taskkillTree(child.pid);
    }
    if (!args.keepProfile) {
      for (let i = 0; i < 6; i++) {
        try {
          fs.rmSync(profileDir, { recursive: true, force: true });
          break;
        } catch {
          await sleep(350);
        }
      }
    } else {
      log(`[audit] kept profile: ${profileDir}`);
    }
  };

  try {
    /* ---- wait for /json/version, then attach over WebSocket ---- */
    let version = null;
    try {
      version = await waitForDeadline(
        async () => {
          const r = await httpJson(`http://127.0.0.1:${debugPort}/json/version`, { timeoutMs: 2000 });
          return r.statusCode === 200 ? JSON.parse(r.body) : null;
        },
        { timeoutMs: 25000, intervalMs: 250, label: `Chrome /json/version on :${debugPort}` }
      );
    } catch (err) {
      throw new Error(
        `Chrome DevTools endpoint never came up: ${err.message}\n` +
          `chrome stdio tail:\n${chromeStdioLog.slice(-1500)}`
      );
    }
    chromeVersion = version.Browser || "unknown";
    log(`[audit] ${chromeVersion}  ws=${version.webSocketDebuggerUrl}`);

    cdp = await Cdp.connect(version.webSocketDebuggerUrl, 15000);

    // Keep the tap dispatch wired up.
    const origOnMessage = cdp._onMessage.bind(cdp);
    cdp._onMessage = (ev) => {
      origOnMessage(ev);
      try {
        const data = ev.data;
        const msg = JSON.parse(typeof data === "string" ? data : "{}");
        if (msg.method) cdp._dispatchTaps(msg.method, msg.params || {});
      } catch { /* ignore */ }
    };

    const target = await cdp.send("Target.createTarget", { url: "about:blank" });
    const attached = await cdp.send("Target.attachToTarget", { targetId: target.targetId, flatten: true });
    const sid = attached.sessionId;
    cdp.sessionId = sid;

    await cdp.send("Page.enable", {}, sid);
    await cdp.send("Runtime.enable", {}, sid);
    await cdp.send("Network.enable", {}, sid);
    await cdp.send("Network.setExtraHTTPHeaders", {
      headers: withAuth({ "Cache-Control": "no-cache" }),
    }, sid);
    if (args.blockExternal) {
      await cdp.send("Network.setBlockedURLs", {
        urls: ["*unpkg.com*", "*cdn.jsdelivr.net*", "*googleapis.com*", "*fonts.gstatic.com*", "*githubusercontent.com*"],
      }, sid);
      log("[audit] --block-external: third-party hosts blocked (offline-safe run)");
    }

    // Network-idle accounting driven by real CDP events.
    let inFlight = 0;
    let requestsSeen = 0;
    let lastActivity = Date.now();
    cdp.on("Network.requestWillBeSent", () => { inFlight++; requestsSeen++; lastActivity = Date.now(); });
    cdp.on("Network.loadingFinished", () => { inFlight = Math.max(0, inFlight - 1); lastActivity = Date.now(); });
    cdp.on("Network.loadingFailed", () => { inFlight = Math.max(0, inFlight - 1); lastActivity = Date.now(); });

    async function waitForNetworkIdle(idleMs, maxMs) {
      const t0 = Date.now();
      while (Date.now() - t0 < maxMs) {
        const quietFor = Date.now() - lastActivity;
        if (inFlight <= 0 && quietFor >= idleMs) return true;
        await sleep(100);
      }
      return false;
    }

    /* ---- viewport x route loop ---- */
    let navCounter = 0;
    for (const vp of args.viewports) {
      const mobile = vp.width < 768;
      try {
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width: vp.width,
          height: vp.height,
          deviceScaleFactor: 1,
          mobile,
          screenWidth: vp.width,
          screenHeight: vp.height,
        }, sid);
      } catch (err) {
        // Non-deprecated domain first; fall back to the Page alias.
        await cdp.send("Page.setDeviceMetricsOverride", {
          width: vp.width,
          height: vp.height,
          deviceScaleFactor: 1,
          mobile,
        }, sid);
      }
      await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: mobile, maxTouchPoints: mobile ? 5 : 1 }, sid).catch(() => {});

      for (const route of args.routes) {
        navCounter++;
        const u = new URL(base + "/");
        u.searchParams.set("_audit", String(navCounter));
        u.hash = route ? "#" + route : "";
        const navUrl = u.toString();
        const slug = slugRoute(route);
        const shotName = `${vp.width}x${vp.height}-${slug}.png`;
        const shotPath = path.join(args.outDir, shotName);

        const rec = {
          viewport: { width: vp.width, height: vp.height, mobile },
          route,
          url: navUrl,
          generatedAt: new Date().toISOString(),
          status: "ok",
          measurement: null,
          layoutMetrics: null,
          screenshot: null,
          screenshotBytes: 0,
          screenshotFold: null,
          screenshotFoldBytes: 0,
          loadEventFired: false,
          networkIdle: false,
          requestsDuringSettle: 0,
          navAttempts: 0,
          errors: [],
        };

        // Navigate + measure, retried once. A blank/never-loaded document must
        // never be reported as PASS: docScrollWidth==clientWidth is trivially
        // true on an empty page.
        const MAX_NAV_ATTEMPTS = 2;
        for (let attempt = 1; attempt <= MAX_NAV_ATTEMPTS; attempt++) {
          rec.navAttempts = attempt;
          rec.status = "ok";
          navCounter++;
          u.searchParams.set("_audit", String(navCounter));
          const tryUrl = u.toString();
          rec.url = tryUrl;

          // Arm the load waiter BEFORE navigating so a fast load cannot be missed.
          const loadWait = cdp
            .once("Page.loadEventFired", sid, args.loadTimeoutMs)
            .then(() => true)
            .catch(() => false);

          const navRes = await cdp.send("Page.navigate", { url: tryUrl }, sid, args.navTimeoutMs);
          if (navRes.errorText) rec.errors.push("Page.navigate errorText=" + navRes.errorText);
          rec.loadEventFired = await loadWait;
          const reqBefore = requestsSeen;
          rec.networkIdle = await waitForNetworkIdle(args.idleMs, Math.max(1500, args.settleMs));
          rec.requestsDuringSettle = requestsSeen - reqBefore;
          await sleep(args.settleMs);

          // 1) real in-page geometry
          const expr = `(${pageMeasure.toString()})(${JSON.stringify({
            maxOffenders: args.maxOffenders,
            maxWordChecks: args.maxWordChecks,
          })})`;
          const evalRes = await cdp.send("Runtime.evaluate", {
            expression: expr,
            returnByValue: true,
            awaitPromise: false,
          }, sid, 60000);
          if (evalRes.exceptionDetails) {
            rec.errors.push("Runtime.evaluate exception: " + JSON.stringify(evalRes.exceptionDetails).slice(0, 500));
            rec.status = "measure-error";
          } else {
            const raw = evalRes.result && evalRes.result.value;
            try {
              rec.measurement = typeof raw === "string" ? JSON.parse(raw) : raw;
              if (rec.measurement && rec.measurement.error) {
                rec.status = "measure-error";
                rec.errors.push("pageMeasure error: " + rec.measurement.error);
              }
            } catch (err) {
              rec.status = "measure-error";
              rec.errors.push("cannot parse measurement JSON: " + err.message + " raw=" + String(raw).slice(0, 300));
            }
          }

          // 2) independent CDP-side cross-check of layout size
          rec.layoutMetrics = null;
          try {
            const lm = await cdp.send("Page.getLayoutMetrics", {}, sid, 15000);
            const css = lm.cssLayoutViewport || lm.layoutViewport || {};
            rec.layoutMetrics = {
              contentWidth: lm.cssContentSize ? lm.cssContentSize.width : undefined,
              contentHeight: lm.cssContentSize ? lm.cssContentSize.height : undefined,
              layoutViewportWidth: css.clientWidth,
              layoutViewportHeight: css.clientHeight,
              visualViewportWidth: lm.visualViewport ? lm.visualViewport.clientWidth : undefined,
            };
          } catch (err) {
            rec.errors.push("Page.getLayoutMetrics failed: " + err.message);
          }

          const blankReason = blankPageReason(rec, vp);
          if ((!rec.loadEventFired || blankReason) && attempt < MAX_NAV_ATTEMPTS) {
            rec.errors.push(
              `retry ${attempt}: loadEventFired=${rec.loadEventFired}${blankReason ? " blank(" + blankReason + ")" : ""}`
            );
            rec.measurement = null;
            try { await cdp.send("Page.navigate", { url: "about:blank" }, sid, 10000); } catch { /* ignore */ }
            await sleep(300);
            continue;
          }
          if (!rec.loadEventFired) {
            rec.status = "load-timeout";
            rec.errors.push(`Page.loadEventFired not received within ${args.loadTimeoutMs}ms`);
          } else if (blankReason) {
            rec.status = "blank-page";
            rec.errors.push("page looks empty after navigation: " + blankReason);
          }
          break;
        }

        // 3) screenshots: full page (spec name) + viewport-only "fold" copy that
        //    stays previewable (full-page captures can exceed 8000px tall).
        try {
          const shot = await cdp.send("Page.captureScreenshot", {
            format: "png",
            captureBeyondViewport: true,
            fromSurface: true,
          }, sid, 45000);
          const buf = Buffer.from(shot.data, "base64");
          fs.writeFileSync(shotPath, buf);
          rec.screenshot = path.relative(REPO_ROOT, shotPath).replace(/\\/g, "/");
          rec.screenshotBytes = buf.length;
        } catch (err) {
          rec.status = rec.status === "ok" ? "screenshot-error" : rec.status;
          rec.errors.push("Page.captureScreenshot failed: " + err.message);
        }
        try {
          const foldPath = path.join(args.outDir, `${vp.width}x${vp.height}-${slug}-fold.png`);
          const shot2 = await cdp.send("Page.captureScreenshot", {
            format: "png",
            captureBeyondViewport: false,
            fromSurface: true,
          }, sid, 45000);
          const buf2 = Buffer.from(shot2.data, "base64");
          fs.writeFileSync(foldPath, buf2);
          rec.screenshotFold = path.relative(REPO_ROOT, foldPath).replace(/\\/g, "/");
          rec.screenshotFoldBytes = buf2.length;
        } catch (err) {
          rec.errors.push("viewport screenshot failed: " + err.message);
        }

        results.push(rec);
        writeReport();

        const hOver = rec.measurement && Number.isFinite(rec.measurement.horizontalOverflowPx)
          ? rec.measurement.horizontalOverflowPx
          : null;
        const nOff = rec.measurement ? rec.measurement.offenderCount : null;
        log(
          `[audit] ${pad(vp.width + "x" + vp.height, 10)} ${pad("#" + slug, 14)} ` +
            `overflow=${pad(hOver === null ? "n/a" : hOver, 6)} offenders=${pad(nOff === null ? "n/a" : nOff, 4)} ` +
            `-> ${rec.screenshot || "(no screenshot)"}${rec.errors.length ? "  [" + rec.errors.length + " warning(s)]" : ""}`
        );
        if (args.verbose && rec.errors.length) rec.errors.forEach((e) => warn("        ! " + e));
      }
    }
  } catch (err) {
    fatal = err;
    if (!results.length) mode = "failed";
    results.forEach((r) => { if (!r.measurement) r.status = r.status === "ok" ? "harness-error" : r.status; });
  } finally {
    await cleanup();
  }

  /* ---- final report + stdout table ---- */
  const summary = buildSummary(args, results);
  const report = {
    generatedAt: new Date().toISOString(),
    tool: "tools/ui-audit/audit.mjs",
    mode,
    chrome: chromeVersion,
    targetUrl: base,
    options: {
      routes: args.routes,
      viewports: args.viewports,
      settleMs: args.settleMs,
      idleMs: args.idleMs,
      failWidths: args.failWidths,
      blockExternal: args.blockExternal,
    },
    summary,
    results,
    fatalError: fatal ? String(fatal.message || fatal) : null,
  };
  writeReport(report);

  log("");
  log("viewport   route          overflowPx  offenders  pageLvl  badWrap  textOut  status  screenshot");
  log("-".repeat(112));
  for (const r of results) {
    const m = r.measurement || {};
    const isFail = args.failWidths.includes(r.viewport.width);
    const hOver = Number.isFinite(m.horizontalOverflowPx) ? m.horizontalOverflowPx : null;
    let status;
    if (r.status !== "ok" || hOver === null) status = "ERROR";
    else if (hOver > 0) status = isFail ? "FAIL" : "warn";
    else status = "PASS";
    const badWrap = m.textNodesWrappingBadly === null || m.textNodesWrappingBadly === undefined
      ? "n/a"
      : String(m.textNodesWrappingBadly.length);
    const tOut = Array.isArray(m.textOverflowingOwnBox) ? m.textOverflowingOwnBox : null;
    const tOutVisible = tOut === null ? null : tOut.filter((t) => !t.ancestorClipped).length;
    const tOutStr = tOut === null ? "n/a" : tOutVisible === tOut.length ? String(tOut.length) : tOutVisible + "/" + tOut.length;
    if (tOutVisible) status += "*";
    log(
      `${pad(r.viewport.width + "x" + r.viewport.height, 10)} ${pad("#" + slugRoute(r.route), 14)} ` +
        `${pad(hOver === null ? "n/a" : hOver, 11)} ${pad(m.offenderCount === undefined ? "n/a" : m.offenderCount, 10)} ` +
        `${pad(m.pageLevelOffenderCount === undefined ? "n/a" : m.pageLevelOffenderCount, 8)} ` +
        `${pad(badWrap, 8)} ${pad(tOutStr, 8)} ${pad(status, 7)} ${r.screenshot || "-"}`
    );
    for (const e of r.errors) log(`    ! ${e}`);
  }
  log("-".repeat(112));
  log("pageLvl = offenders NOT inside a clipping/scrollable ancestor (the ones that matter).");
  log("textOut = visible/clipped labels whose text paints outside their own box (* = present).");

  /* labels painting outside their own box - the strongest signal of visual collision */
  const tOutRecs = results.filter(
    (r) => r.measurement && Array.isArray(r.measurement.textOverflowingOwnBox) && r.measurement.textOverflowingOwnBox.length
  );
  log("");
  log("TEXT OUTSIDE ITS OWN BOX (label collides with neighbours; no page overflow needed):");
  if (!tOutRecs.length) {
    log("  none detected");
  }
  for (const r of tOutRecs) {
    for (const t of r.measurement.textOverflowingOwnBox.slice(0, 12)) {
      log(
        `  ${pad(r.viewport.width + "x" + r.viewport.height, 10)} +${pad(t.overflowPx, 7)}px  ` +
          `${pad(t.tag + (t.id ? "#" + t.id : ""), 22)} box=${pad(t.boxWidth, 7)} textRight=${pad(t.textRight, 8)} ` +
          `white-space=${t.whiteSpace} flex-shrink=${t.flexShrink}` +
          `${t.ancestorClipped ? " [clipped by ancestor]" : ""}  "${t.text}"  ${t.path}`
      );
    }
  }

  /* top offenders, mobile first */
  const mobileRecs = results.filter((r) => r.viewport.width < 768 && r.measurement);
  if (mobileRecs.length) {
    log("");
    log("TOP OFFENDERS (mobile viewports; page-level = not inside a scroll/clip ancestor):");
    for (const r of mobileRecs) {
      const m = r.measurement;
      const pageLevel = (m.offenders || []).filter((o) => !o.inScrollContainer);
      const clipped = (m.offenders || []).filter((o) => o.inScrollContainer);
      log(`  ${r.viewport.width}x${r.viewport.height} #${slugRoute(r.route)}  pageOverflow=${m.horizontalOverflowPx}px  pageLevel=${m.pageLevelOffenderCount ?? pageLevel.length}  totalFlagged=${m.offenderCount ?? 0}`);
      if (!pageLevel.length) {
        log(`    (no page-level offenders - all ${m.offenderCount ?? 0} flagged boxes sit inside a scrollable/clipping container)`);
      }
      for (const o of pageLevel.slice(0, 8)) {
        log(
          `    PAGE-LEVEL +${pad(o.overflowPx, 7)}px  ${pad(o.tag + (o.id ? "#" + o.id : ""), 20)} ` +
            `${pad(o.reason, 12)} ${o.path}`
        );
      }
      for (const o of clipped.slice(0, 3)) {
        log(
          `    in-scroll  +${pad(o.overflowPx, 7)}px  ${pad(o.tag + (o.id ? "#" + o.id : ""), 20)} ` +
            `${pad(o.reason, 12)} ${o.path.slice(0, 90)}`
        );
      }
    }
  }

  /* words broken across lines (Range.getClientRects evidence) */
  const wrapRecs = results.filter(
    (r) => r.measurement && Array.isArray(r.measurement.textNodesWrappingBadly) && r.measurement.textNodesWrappingBadly.length
  );
  log("");
  log("SINGLE-WORD LINE-BREAKS (Range.getClientRects evidence):");
  if (!wrapRecs.length) {
    log("  none detected");
  }
  for (const r of wrapRecs) {
    for (const w of r.measurement.textNodesWrappingBadly) {
      log(
        `  ${pad(r.viewport.width + "x" + r.viewport.height, 10)} "${w.word}" spans ${w.lines} lines  ` +
          `cause=${w.cause}  ${w.path}`
      );
    }
  }

  log("");
  log(`mode=${mode}  chrome=${chromeVersion}  report=${path.relative(REPO_ROOT, path.join(args.outDir, "report.json")).replace(/\\/g, "/")}`);
  log(
    `summary: ${summary.passCount}/${results.length} viewport-routes clean; ` +
      `mobileOverflowFailures=${summary.mobileOverflowFailures.length}; ` +
      `worstPageOverflowPx=${summary.worstPageOverflowPx}`
  );

  if (srvHandle) {
    log("[audit] stopping spawned uvicorn ...");
    await srvHandle.stop();
  }

  if (fatal) {
    warn("\n[audit] FATAL: " + (fatal.stack || fatal.message));
    return 2;
  }
  if (summary.mobileOverflowFailures.length) return 1;
  return 0;

  /* ------------------------------------------------------------------ */

  function writeReport(explicit) {
    const report = explicit || currentReport();
    const tmp = path.join(args.outDir, "report.json.tmp");
    fs.writeFileSync(tmp, JSON.stringify(report, null, 2));
    fs.renameSync(tmp, path.join(args.outDir, "report.json"));
  }

  function currentReport() {
    return {
      generatedAt: new Date().toISOString(),
      tool: "tools/ui-audit/audit.mjs",
      mode,
      chrome: chromeVersion,
      targetUrl: base,
      options: {
        routes: args.routes,
        viewports: args.viewports,
        settleMs: args.settleMs,
        idleMs: args.idleMs,
        failWidths: args.failWidths,
        failOnTextOverflow: args.failOnTextOverflow,
        blockExternal: args.blockExternal,
      },
      summary: buildSummary(args, results),
      results,
    };
  }
}

/**
 * Detect a document that never really rendered. docScrollWidth === clientWidth
 * is trivially true on an empty page, so an unloaded page must be reported as a
 * failure instead of a PASS.
 */
function blankPageReason(rec, vp) {
  const m = rec.measurement;
  if (!m) return "no measurement";
  if (m.error) return "measurement error";
  const markers = m.appMarkers || {};
  const textLen = Number(markers.bodyTextLength || m.bodyTextLength || 0);
  const kids = Number(m.bodyChildCount || 0);
  const hasChrome = !!(markers.navRail || markers.main);
  if (kids <= 1) return "bodyChildCount=" + kids;
  if (!hasChrome) return "app chrome missing (nav#navRail / main not found)";
  if (textLen < 40) return "visible body text length=" + textLen;
  return null;
}

function buildSummary(args, results) {
  const mobileOverflowFailures = [];
  let worstPageOverflowPx = 0;
  let passCount = 0;
  let badWrapTotal = 0;
  let offenderTotal = 0;
  let pageLevelOffenderTotal = 0;
  let textOverflowTotal = 0;
  let textOverflowUnclippedTotal = 0;
  for (const r of results) {
    const m = r.measurement || {};
    const h = Number.isFinite(m.horizontalOverflowPx) ? m.horizontalOverflowPx : 0;
    if (h > worstPageOverflowPx) worstPageOverflowPx = h;
    if (r.status === "ok" && h <= 0) passCount++;
    const textOut = Array.isArray(m.textOverflowingOwnBox) ? m.textOverflowingOwnBox : [];
    const textOutVisible = textOut.filter((t) => !t.ancestorClipped).length;
    textOverflowTotal += textOut.length;
    textOverflowUnclippedTotal += textOutVisible;
    if (Array.isArray(m.textNodesWrappingBadly)) badWrapTotal += m.textNodesWrappingBadly.length;
    if (Number.isFinite(m.offenderCount)) offenderTotal += m.offenderCount;
    if (Number.isFinite(m.pageLevelOffenderCount)) pageLevelOffenderTotal += m.pageLevelOffenderCount;
    if (
      args.failWidths.includes(r.viewport.width) &&
      (h > 0 || r.status !== "ok" || (args.failOnTextOverflow && textOutVisible > 0))
    ) {
      mobileOverflowFailures.push({
        viewport: r.viewport.width + "x" + r.viewport.height,
        route: r.route,
        horizontalOverflowPx: m.horizontalOverflowPx ?? null,
        visibleTextOverflows: textOutVisible,
        status: r.status,
      });
    }
  }
  return {
    passCount,
    total: results.length,
    mobileOverflowFailures,
    worstPageOverflowPx,
    offenderTotal,
    pageLevelOffenderTotal,
    badWrapTotal,
    textOverflowTotal,
    textOverflowUnclippedTotal,
  };
}

/* ===================================================================== */
/* Entry point (only when executed directly - probe.mjs imports from here) */
/* ===================================================================== */

const isDirect = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isDirect) {
  let exitCode = 0;
  try {
    exitCode = await main();
  } catch (err) {
    warn("[audit] FATAL " + (err && (err.stack || err.message || err)));
    exitCode = 2;
  }
  process.exit(exitCode);
}

export { Cdp, pageMeasure, buildSummary, blankPageReason, parseArgs, findFreePort, httpJson, slugRoute, sleep, pad };

