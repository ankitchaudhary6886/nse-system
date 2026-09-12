// Deployment status card — reads /api/deployment-check.
// Shows check results as green/red rows.

async function loadDeployment() {
  const box = document.getElementById("deploymentBox");
  const badge = document.getElementById("deploymentBadge");
  if (!box) return;
  try {
    const data = await api("/api/deployment-check");
    const checks = data.checks || [];
    const fails = data.fails || 0;
    if (badge) {
      badge.textContent = data.summary || "—";
      badge.className = fails === 0 ? "badge good" : "badge muted";
    }
    let html = `<div style="font-size:12px; color:#7f8da9; margin-bottom:8px;">${data.time || ""}</div>`;
    checks.forEach(c => {
      const icon = c.ok ? "✓" : "✗";
      const color = c.ok ? "#34d399" : "#fb7185";
      html += `<div class="level" style="padding:8px 12px;">
        <span style="color:${color}; font-weight:bold; min-width:20px; display:inline-block;">${icon}</span>
        <span style="flex:1; margin-left:8px;">${c.label}</span>
        <strong style="color:#9fb0cc; font-size:12px;">${c.detail || ""}</strong>
      </div>`;
    });
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<p>Deployment check unavailable: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadDeployment();
  const btn = document.getElementById("refreshBtn");
  if (btn) {
    btn.addEventListener("click", loadDeployment);
  }
});