/* ⚡ One-click data refresh panel (2026-10-18).
 *
 * Why: the owner cannot run commands daily. This injects a small floating
 * panel into every terminal page. It shows whether the data is current, offers
 * a single "Refresh now" button that runs the whole server-side chain, shows
 * per-step progress, and reloads the page when it finishes so every view
 * reflects the new data. It also contains the optional Fyers login (paste the
 * auth code once) and a token-refresh button.
 *
 * The panel is self-contained (own CSS, own DOM, no build step) and degrades
 * silently if the backend is older than these endpoints: every fetch is
 * wrapped, and the panel simply stays hidden when /api/data/health 404s.
 */
(function () {
  "use strict";
  if (window.__dshRefreshPanel) return;
  window.__dshRefreshPanel = true;

  var POLL_MS = 30000;
  var RUN_POLL_MS = 2000;
  var runPoll = null;
  var healthTimer = null;

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "style") node.setAttribute("style", attrs[k]);
      else if (k.indexOf("on") === 0) node.addEventListener(k.slice(2), attrs[k]);
      else node.setAttribute(k, attrs[k]);
    });
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function fmtDate(value) {
    return value ? String(value).slice(0, 10) : "—";
  }

  var css = el("style");
  css.textContent = [
    "#dsh-panel{position:fixed;right:14px;bottom:14px;z-index:2147483000;",
    "font:13px/1.4 system-ui,Segoe UI,Arial;color:#e7ecf3;max-width:340px}",
    "#dsh-panel *{box-sizing:border-box}",
    "#dsh-toggle{background:#152238;border:1px solid #2b3b55;color:#e7ecf3;",
    "border-radius:999px;padding:9px 14px;font-weight:600;cursor:pointer;",
    "box-shadow:0 6px 18px rgba(0,0,0,.4)}",
    "#dsh-toggle.dsh-stale{border-color:#e0a33e;color:#ffd27a}",
    "#dsh-card{margin-top:8px;background:#101a2b;border:1px solid #2b3b55;",
    "border-radius:12px;padding:12px;box-shadow:0 10px 28px rgba(0,0,0,.5);display:none}",
    "#dsh-card.open{display:block}",
    "#dsh-card h4{margin:0 0 6px;font-size:13px;letter-spacing:.02em;color:#9fb3cc}",
    ".dsh-row{display:flex;justify-content:space-between;gap:8px;margin:3px 0}",
    ".dsh-row span:last-child{text-align:right;color:#cfe0f5}",
    ".dsh-ok{color:#4ade80!important}.dsh-bad{color:#f87171!important}",
    ".dsh-warn{color:#fbbf24!important}",
    ".dsh-btn{display:block;width:100%;margin-top:8px;background:#2563eb;border:0;",
    "color:#fff;border-radius:8px;padding:9px;font-weight:600;cursor:pointer}",
    ".dsh-btn[disabled]{opacity:.55;cursor:default}",
    ".dsh-btn.alt{background:#1f2f47;border:1px solid #31465f;color:#dce7f5}",
    ".dsh-input{width:100%;margin-top:6px;padding:8px;border-radius:8px;",
    "border:1px solid #31465f;background:#0b1422;color:#e7ecf3}",
    ".dsh-note{margin-top:6px;color:#8fa3bb;font-size:11.5px}",
    ".dsh-progress{margin-top:8px;height:6px;border-radius:999px;background:#1b2a40;overflow:hidden}",
    ".dsh-progress>i{display:block;height:100%;width:0;background:#2563eb;transition:width .3s}",
    "#dsh-msg{margin-top:8px;color:#cfe0f5;font-size:12px;white-space:pre-wrap}",
    "@media(max-width:520px){#dsh-panel{right:8px;bottom:8px;left:8px;max-width:none}}"
  ].join("");
  document.head.appendChild(css);

  var toggle = el("button", { id: "dsh-toggle", title: "Data refresh" }, "⚡ Data");
  var card = el("div", { id: "dsh-card" });
  var panel = el("div", { id: "dsh-panel" });
  panel.appendChild(toggle);
  panel.appendChild(card);

  var rows = {};
  function row(label, key, cls) {
    var r = el("div", { class: "dsh-row" });
    r.appendChild(el("span", null, label));
    rows[key] = el("span", { class: cls || "" }, "…");
    r.appendChild(rows[key]);
    card.appendChild(r);
    return rows[key];
  }

  card.appendChild(el("h4", null, "DATA STATUS"));
  row("Prices", "price");
  row("Data gate", "gate");
  row("Fyers", "fyers");
  row("Last refresh", "refresh");
  var progress = el("div", { class: "dsh-progress" });
  var bar = el("i");
  progress.appendChild(bar);
  card.appendChild(progress);
  var msg = el("div", { id: "dsh-msg" });
  card.appendChild(msg);
  var refreshBtn = el("button", { class: "dsh-btn" }, "Refresh data now");
  card.appendChild(refreshBtn);

  // Fyers section (collapsed unless needed)
  var fyersBox = el("div", { style: "margin-top:10px;border-top:1px solid #22324a;padding-top:8px" });
  fyersBox.appendChild(el("h4", null, "FYERS LOGIN (optional)"));
  var loginBtn = el("button", { class: "dsh-btn alt" }, "1. Open Fyers login");
  var codeInput = el("input", { class: "dsh-input", placeholder: "paste auth_code here" });
  var saveBtn = el("button", { class: "dsh-btn alt" }, "2. Save auth code");
  var refreshTokenBtn = el("button", { class: "dsh-btn alt" }, "Auto-renew token");
  var fyersNote = el("div", { class: "dsh-note" },
    "Opens the broker login in a new tab. Log in, approve, then copy the " +
    "auth_code value from the redirected address bar and paste it above. " +
    "Fyers is optional: free sources refresh prices without it.");
  fyersBox.appendChild(loginBtn);
  fyersBox.appendChild(codeInput);
  fyersBox.appendChild(saveBtn);
  fyersBox.appendChild(refreshTokenBtn);
  fyersBox.appendChild(fyersNote);
  card.appendChild(fyersBox);

  function setRows(health) {
    if (!health) return;
    var price = health.prices_rows
      ? health.prices_rows.toLocaleString() + " rows"
      : "no data";
    rows.price.className = "";
    rows.price.textContent = fmtDate(health.max_price_date) + " · " + price;
    var fresh = health.freshness || {};
    if (fresh.blocked) {
      rows.gate.className = "dsh-bad";
      rows.gate.textContent = "STALE — signals paused";
      toggle.classList.add("dsh-stale");
    } else {
      rows.gate.className = "dsh-ok";
      rows.gate.textContent = "fresh (0 missing sessions)";
      toggle.classList.remove("dsh-stale");
    }
    var fyers = health.fyers || {};
    var token = fyers.token || {};
    if (token.present && token.expired === false) {
      rows.fyers.className = "dsh-ok";
      rows.fyers.textContent = "connected";
    } else {
      rows.fyers.className = "dsh-warn";
      rows.fyers.textContent = token.present ? "token expired" : "not logged in (optional)";
    }
    var last = health.last_refresh || {};
    rows.refresh.className = "";
    rows.refresh.textContent = last.finished_at
      ? fmtDate(last.finished_at) + " " + (last.status || "")
      : "never";
  }

  function getJSON(url, opts) {
    return fetch(url, opts || { headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json(); });
  }

  function loadHealth() {
    return getJSON("/api/data/health").then(function (h) {
      setRows(h);
      return h;
    }).catch(function () { /* older backend: keep panel hidden */ });
  }

  function pollRun() {
    if (runPoll) clearTimeout(runPoll);
    getJSON("/api/refresh/status").then(function (s) {
      if (!s) return;
      var total = s.total || 0;
      var index = s.index || 0;
      bar.style.width = total ? Math.round(100 * index / total) + "%" : "0%";
      if (s.running) {
        msg.textContent = s.message || "Refreshing…";
        runPoll = setTimeout(pollRun, RUN_POLL_MS);
      } else {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh data now";
        bar.style.width = "100%";
        var latest = s.latest_run || {};
        if (latest.status === "ok") {
          msg.textContent = "✅ Refresh complete — reloading new data…";
          setTimeout(function () { window.location.reload(); }, 1800);
        } else if (latest.status === "partial") {
          var failed = (latest.steps || []).filter(function (x) { return !x.ok; })
            .map(function (x) { return x.name; });
          msg.textContent = "⚠️ Partly refreshed. Failed: " + failed.join(", ") +
            " — reloading…";
          setTimeout(function () { window.location.reload(); }, 2500);
        } else {
          msg.textContent = "❌ Refresh failed: " + (s.message || latest.error || "unknown");
        }
        loadHealth();
      }
    }).catch(function () {
      refreshBtn.disabled = false;
      msg.textContent = "Could not read refresh status.";
    });
  }

  refreshBtn.addEventListener("click", function () {
    refreshBtn.disabled = true;
    refreshBtn.textContent = "Refreshing…";
    msg.textContent = "Starting refresh…";
    getJSON("/api/refresh", { method: "POST", headers: { "Accept": "application/json" } })
      .then(function (r) {
        if (r && r.started === false) {
          msg.textContent = "A refresh is already running; showing its progress…";
        }
        pollRun();
      })
      .catch(function () {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh data now";
        msg.textContent = "Could not start a refresh.";
      });
  });

  loginBtn.addEventListener("click", function () {
    getJSON("/api/fyers/login-url").then(function (r) {
      if (r && r.ok && r.url) window.open(r.url, "_blank", "noopener");
      else msg.textContent = "Login URL unavailable: " + ((r && r.error) || "unknown");
    }).catch(function () { msg.textContent = "Login endpoint unavailable."; });
  });

  saveBtn.addEventListener("click", function () {
    var code = (codeInput.value || "").trim();
    if (!code) { msg.textContent = "Paste the auth_code first."; return; }
    saveBtn.disabled = true;
    getJSON("/api/fyers/exchange", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code })
    }).then(function (r) {
      saveBtn.disabled = false;
      if (r && r.ok) {
        codeInput.value = "";
        msg.textContent = "✅ Fyers connected. Token stored until " +
          (r.expires_at || "next morning");
        loadHealth();
      } else {
        msg.textContent = "❌ Fyers login failed: " + ((r && r.error) || "unknown");
      }
    }).catch(function () {
      saveBtn.disabled = false;
      msg.textContent = "Could not save the auth code.";
    });
  });

  refreshTokenBtn.addEventListener("click", function () {
    refreshTokenBtn.disabled = true;
    getJSON("/api/fyers/refresh", { method: "POST", headers: { "Accept": "application/json" } })
      .then(function (r) {
        refreshTokenBtn.disabled = false;
        if (r && r.ok) {
          msg.textContent = "✅ Token renewed until " + (r.expires_at || "next morning");
          loadHealth();
        } else {
          msg.textContent = "Token renewal failed: " + ((r && r.error) || "unknown");
        }
      }).catch(function () {
        refreshTokenBtn.disabled = false;
        msg.textContent = "Token renewal endpoint unavailable.";
      });
  });

  toggle.addEventListener("click", function () {
    card.classList.toggle("open");
    if (card.classList.contains("open")) loadHealth();
  });

  document.body.appendChild(panel);
  loadHealth();
  healthTimer = setInterval(loadHealth, POLL_MS);
})();
