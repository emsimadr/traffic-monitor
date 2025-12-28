async function saveConfig() {
  const btn = document.getElementById("saveConfigBtn");
  const status = document.getElementById("saveStatus");
  const ta = document.getElementById("configText");
  if (!btn || !status || !ta) return;

  btn.disabled = true;
  status.textContent = "Saving...";
  try {
    let overrides;
    try {
      overrides = JSON.parse(ta.value);
    } catch (e) {
      throw new Error("Overrides must be valid JSON in v0.");
    }

    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ overrides }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Save failed (${res.status})`);
    }
    status.textContent = "Saved.";
  } catch (e) {
    status.textContent = String(e.message || e);
  } finally {
    btn.disabled = false;
  }
}

async function refreshLogs() {
  const pre = document.getElementById("logsPre");
  if (!pre) return;
  pre.textContent = "(loading...)";
  const res = await fetch("/api/logs/tail?lines=200");
  const data = await res.json();
  pre.textContent = (data.lines || []).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const saveBtn = document.getElementById("saveConfigBtn");
  if (saveBtn) saveBtn.addEventListener("click", saveConfig);

  const refreshBtn = document.getElementById("refreshLogsBtn");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshLogs);

  if (document.getElementById("logsPre")) refreshLogs();
});


