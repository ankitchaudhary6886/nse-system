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
      const subtitle = `score ${p.score}`;
      const primary = `₹${p.close} · EMA50 ₹${p.ema50} · EMA200 ₹${p.ema200}`;
      const secondary = p.notes || "";
      box.appendChild(window.renderUnifiedCard({
        symbol: p.symbol, subtitle, primary, secondary,
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
      const subtitle = `₹${p.last_price}`;
      const primary = `Q${p.quality_score}/T${p.trend_score}/V${p.value_score} · composite ${p.composite}`;
      const secondary = p.notes || "";
      box.appendChild(window.renderUnifiedCard({
        symbol: p.symbol, badges, subtitle, primary, secondary,
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
      const subtitle = `₹${p.last_price} · ${below}% off 52w high`;
      const primary = `Q${p.quality_score}/V${p.value_score} · composite ${p.composite}`;
      const secondary = p.notes || "";
      box.appendChild(window.renderUnifiedCard({
        symbol: p.symbol, badges, subtitle, primary, secondary,
      }));
    });
  } catch (e) {
    box.innerHTML = `<p>Value Radar error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadTrendPanel();
  loadPositionalPanel();
  loadValueRadarPanel();
  const btn = document.getElementById("refreshBtn");
  if (btn) {
    btn.addEventListener("click", () => {
      loadTrendPanel();
      loadPositionalPanel();
      loadValueRadarPanel();
    });
  }
});