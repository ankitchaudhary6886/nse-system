#!/usr/bin/env node
/**
 * tools/ui-audit/serve.mjs
 *
 * Dependency-free helper that starts the NSE Research FastAPI terminal for the
 * UI audit harness, waits until /api/health answers, and then stays alive until
 * it is killed (Ctrl+C / taskkill).
 *
 * Only Node builtins are used - npm is assumed to be offline.
 *
 * Standalone:
 *   node tools/ui-audit/serve.mjs
 *   node tools/ui-audit/serve.mjs --port 8011
 *
 * As a library (used by audit.mjs --spawn-server):
 *   import { startServer } from "./serve.mjs";
 *   const srv = await startServer({ port: 8011 });
 *   ...
 *   await srv.stop();
 */

import http from "node:http";
import net from "node:net";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const OUT_DIR = path.join(__dirname, "out");

export const DEFAULT_HOST = "127.0.0.1";
export const DEFAULT_PORT = 8011;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Resolve the repo virtualenv python (Windows + POSIX shapes). */
export function resolvePython(repoRoot = REPO_ROOT) {
  const candidates = [
    path.join(repoRoot, "env", "Scripts", "python.exe"),
    path.join(repoRoot, "env", "bin", "python"),
    path.join(repoRoot, ".venv", "Scripts", "python.exe"),
  ];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  return null;
}

/** True when a TCP port on host is free. */
export function isPortFree(port, host = DEFAULT_HOST) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.once("error", () => resolve(false));
    srv.once("listening", () => srv.close(() => resolve(true)));
    srv.listen(port, host);
  });
}

/** Ask the OS for a free ephemeral port. */
export function findFreePort(host = DEFAULT_HOST) {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once("error", reject);
    srv.listen(0, host, () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

/** Minimal HTTP GET returning { statusCode, body }. */
export function httpGet(url, { headers = {}, timeoutMs = 5000 } = {}) {
  return new Promise((resolve, reject) => {
    let req;
    try {
      req = http.get(url, { headers }, (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () =>
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            body: Buffer.concat(chunks).toString("utf8"),
          })
        );
      });
    } catch (err) {
      reject(err);
      return;
    }
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error("request timeout after " + timeoutMs + "ms: " + url));
    });
    req.on("error", reject);
  });
}

export function basicAuthHeader(user, pass) {
  return "Basic " + Buffer.from(`${user}:${pass}`, "utf8").toString("base64");
}

/**
 * Start uvicorn and wait for /api/health.
 * @returns {Promise<{child, port, host, url, python, log, started:boolean, stop:Function}>}
 */
export async function startServer({
  port = DEFAULT_PORT,
  host = DEFAULT_HOST,
  repoRoot = REPO_ROOT,
  user = process.env.ADMIN_USER || "",
  pass = process.env.ADMIN_PASS || "",
  timeoutMs = 40000,
  autoPickPort = true,
  quiet = false,
} = {}) {
  const log = [];
  const say = (m) => {
    log.push(m);
    if (!quiet) console.log(m);
  };

  const python = resolvePython(repoRoot);
  if (!python) {
    throw new Error(
      "No virtualenv python found. Looked for env\\Scripts\\python.exe under " + repoRoot
    );
  }

  let chosenPort = port;
  if (!(await isPortFree(chosenPort, host))) {
    if (!autoPickPort) {
      throw new Error(`Port ${chosenPort} on ${host} is already in use.`);
    }
    chosenPort = await findFreePort(host);
    say(`[serve] port ${port} busy -> using free port ${chosenPort}`);
  }

  const args = [
    "-m",
    "uvicorn",
    "terminal_api:app",
    "--host",
    host,
    "--port",
    String(chosenPort),
  ];
  say(`[serve] spawn: "${python}" ${args.join(" ")}  (cwd=${repoRoot})`);

  const child = spawn(python, args, {
    cwd: repoRoot,
    windowsHide: true,
    // Keep the pipes tiny: uvicorn access logs are useful when startup fails,
    // so capture them, but never let a full pipe block the child.
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", (d) => log.push("[uvicorn] " + d.toString("utf8").trimEnd()));
  child.stderr.on("data", (d) => log.push("[uvicorn!] " + d.toString("utf8").trimEnd()));
  let exited = null;
  child.on("exit", (code, signal) => {
    exited = { code, signal };
    log.push(`[serve] uvicorn exited code=${code} signal=${signal}`);
  });

  const url = `http://${host}:${chosenPort}`;
  /* No login gate by default: only attach Basic auth when BOTH halves were
     supplied explicitly (ADMIN_USER/ADMIN_PASS or --user/--pass). */
  const auth = user && pass ? { Authorization: basicAuthHeader(user, pass) } : {};
  const deadline = Date.now() + timeoutMs;
  let healthy = false;
  let lastErr = "no attempt";
  while (Date.now() < deadline) {
    if (exited) break;
    try {
      const res = await httpGet(url + "/api/health", { headers: auth, timeoutMs: 4000 });
      if (res.statusCode === 200) {
        healthy = true;
        say(`[serve] /api/health -> 200 ${res.body.slice(0, 120)}`);
        break;
      }
      lastErr = "HTTP " + res.statusCode;
      if (res.statusCode === 401) {
        lastErr += " (target still requires HTTP Basic auth; set ADMIN_USER/ADMIN_PASS or --user/--pass)";
      }
    } catch (err) {
      lastErr = err.message;
    }
    await sleep(400);
  }

  if (!healthy) {
    try {
      child.kill();
    } catch {
      /* ignore */
    }
    throw new Error(
      `uvicorn did not become healthy at ${url}/api/health within ${timeoutMs}ms (last: ${lastErr}).\n` +
        log.slice(-25).join("\n")
    );
  }

  try {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    fs.writeFileSync(
      path.join(OUT_DIR, "server.json"),
      JSON.stringify({ host, port: chosenPort, url, pid: child.pid, startedAt: new Date().toISOString() }, null, 2)
    );
  } catch {
    /* non-fatal */
  }

  const stop = async () => {
    if (exited) return;
    try {
      child.kill();
    } catch {
      /* ignore */
    }
    const t0 = Date.now();
    while (!exited && Date.now() - t0 < 1500) await sleep(100);
    if (!exited && process.platform === "win32" && child.pid) {
      // uvicorn spawns no children normally, but be thorough on Windows.
      try {
        spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
      } catch {
        /* ignore */
      }
    }
  };

  return { child, host, port: chosenPort, url, python, log, started: true, stop };
}

/* ------------------------------ CLI mode ------------------------------ */

function parseCli(argv) {
  const out = { port: DEFAULT_PORT, portExplicit: false, timeoutMs: 40000, keep: true };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--port") {
      out.port = Number(argv[++i]);
      out.portExplicit = true;
    } else if (a === "--host") out.host = argv[++i];
    else if (a === "--user") out.user = argv[++i];
    else if (a === "--pass") out.pass = argv[++i];
    else if (a === "--timeout") out.timeoutMs = Number(argv[++i]) * 1000;
    else if (a === "--help" || a === "-h") out.help = true;
  }
  return out;
}

const isDirect = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isDirect) {
  const cli = parseCli(process.argv.slice(2));
  if (cli.help) {
    console.log(`Usage: node tools/ui-audit/serve.mjs [--host 127.0.0.1] [--port 8011]
                                       [--user <u>] [--pass <pw>] [--timeout 40]

Spawns: <repo>\\env\\Scripts\\python.exe -m uvicorn terminal_api:app --host <host> --port <port>
Polls : http://<host>:<port>/api/health (no auth; terminal_api has no login gate)
        An Authorization header is sent only when BOTH --user and --pass (or
        ADMIN_USER and ADMIN_PASS) are supplied.
Stays : running until killed. Ctrl+C shuts the server down.
Writes: tools/ui-audit/out/server.json { host, port, url, pid }`);
    process.exit(0);
  }
  try {
    const srv = await startServer({
      port: cli.port,
      host: cli.host || DEFAULT_HOST,
      user: cli.user,
      pass: cli.pass,
      timeoutMs: cli.timeoutMs,
      autoPickPort: !cli.portExplicit,
      quiet: false,
    });
    console.log(`\n[serve] READY ${srv.url}`);
    console.log(`[serve] audit with: node tools/ui-audit/audit.mjs --url ${srv.url}`);
    console.log("[serve] press Ctrl+C to stop.\n");

    let stopping = false;
    const shutdown = async (sig) => {
      if (stopping) return;
      stopping = true;
      console.log(`\n[serve] ${sig} received - stopping uvicorn...`);
      await srv.stop();
      process.exit(0);
    };
    process.on("SIGINT", () => shutdown("SIGINT"));
    process.on("SIGTERM", () => shutdown("SIGTERM"));
    // Keep the event loop alive.
    setInterval(() => {}, 1 << 30);
  } catch (err) {
    console.error("[serve] FATAL " + err.message);
    process.exit(3);
  }
}
