// Scanners — Trend, Positional, Value Radar. Uses renderUnifiedCard.

async function loadTrendPanel() {
  const box = document.getElementById("trendList");
  const badge = document.getElementById("trendBadge");
  if (!box) return;
  try {
    const data = await api("/api/trend?n=30");
    const picks = data.candidates || [];
    if (!picks.length) {
      box.innerHTML = "<p>No trend candidates right now.</p>";
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) badge.textContent = `${picks.length} candidates`;
    box.innerHTML = "";
    picks.forEach(p => {
      const subtitle = "EMA50 > EMA200 uptrend";
      const primary = `Close ₹${p.close} · EMA50 ₹${p.ema50} · EMA200 ₹${p.ema200}`;
      const secondary = `Score ${p.score}`;
      box.appendChild(window.renderUnifiedCard({
        symbol: p.symbol, subtitle, primary, secondary, note: p.notes || "",
      }));
    });
  } catch (e) {
    box.innerHTML = `<p>Trend error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

async function loadPositionalPanel() {
  const box = document.getElementById("positionalList");
  const badge = document.getElementById("positionalBadge");
  if (!box) return;
  try {
    const data = await api("/api/positional?n=30");
    const picks = data.picks || [];
    if (!picks.length) {
      box.innerHTML = "<p>No positional candidates right now.</p>";
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) badge.textContent = `${picks.length} candidates`;
    box.innerHTML = "";
    picks.forEach(p => {
      const tierCls = (p.tier === "S" || p.tier === "A") ? "WIN"
                    : p.tier === "B" ? "OPEN" : "PENDING";
      const badges = [`<span class="outcome ${tierCls}">TIER ${p.tier}</span>`];
      const subtitle = "Quality / trend / value blend";
      const primary = `Close ₹${p.last_price} · Composite ${p.composite}`;
      const secondary = `Quality ${p.quality_score} · Trend ${p.trend_score} · Value ${p.value_score}`;
      box.appendChild(window.renderUnifiedCard({
        symbol: p.symbol, badges, subtitle, primary, secondary, note: p.notes || "",
      }));
    });
  } catch (e) {
    box.innerHTML = `<p>Positional error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

async function loadValueRadarPanel() {
  const box = document.getElementById("valueRadarList");
  const badge = document.getElementById("valueRadarBadge");
  if (!box) return;
  try {
    const data = await api("/api/value-radar?n=25");
    const picks = data.picks || [];
    if (!picks.length) {
      box.innerHTML = "<p>No value candidates right now.</p>";
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) badge.textContent = `${picks.length} candidates`;
    box.innerHTML = "";
    picks.forEach(p => {
      const tierCls = p.tier === "A" ? "WIN" : (p.tier === "B" ? "OPEN" : "PENDING");
      const badges = [`<span class="outcome ${tierCls}">TIER ${p.tier}</span>`];
      const below = p.below_52w != null ? (p.below_52w * 100).toFixed(0) : "—";
      const subtitle = "Cheap but solid";
      const primary = `Close ₹${p.last_price} · Composite ${p.composite}`;
      const secondary = `Quality ${p.quality_score} · Value ${p.value_score} · ${below}% off 52w high`;
      box.appendChild(window.renderUnifiedCard({
        symbol: p.symbol, badges, subtitle, primary, secondary, note: p.notes || "",
      }));
    });
  } catch (e) {
    box.innerHTML = `<p>Value Radar error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

window.refreshScannerPanels = () => Promise.all([
  loadTrendPanel(),
  loadPositionalPanel(),
  loadValueRadarPanel(),
]);