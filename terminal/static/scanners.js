// Scanners panel — trend + positional cards.
// Self-contained; hooks into DOMContentLoaded. Loaded after app.js.

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
      const div = document.createElement("div");
      div.className = "stock-card";
      div.innerHTML = `<strong>${p.symbol} · score ${p.score}</strong>
        <span>₹${p.close} · EMA50 ₹${p.ema50} · EMA200 ₹${p.ema200}</span>
        <span>${p.notes || ""}</span>`;
      div.addEventListener("click", () => {
        setView("overview");
        loadSymbol(p.symbol);
      });
      box.appendChild(div);
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
      const div = document.createElement("div");
      div.className = "stock-card";
      const tierClass = p.tier === "S" ? "WIN" :
                        p.tier === "A" ? "WIN" :
                        p.tier === "B" ? "OPEN" : "PENDING";
      div.innerHTML = `<strong>${p.symbol} <span class="outcome ${tierClass}">TIER ${p.tier}</span></strong>
        <span>₹${p.last_price} · Q${p.quality_score}/T${p.trend_score}/V${p.value_score} · composite ${p.composite}</span>
        <span>${p.notes || ""}</span>`;
      div.addEventListener("click", () => {
        setView("overview");
        loadSymbol(p.symbol);
      });
      box.appendChild(div);
    });
  } catch (e) {
    box.innerHTML = `<p>Positional error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadTrendPanel();
  loadPositionalPanel();
  const btn = document.getElementById("refreshBtn");
  if (btn) {
    btn.addEventListener("click", () => {
      loadTrendPanel();
      loadPositionalPanel();
    });
  }
});