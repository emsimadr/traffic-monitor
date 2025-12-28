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

  // Counting quick-edit helpers
  const applyBtn = document.getElementById("applyCountingBtn");
  if (applyBtn) {
    const status = document.getElementById("countingStatus");
    const ta = document.getElementById("configText");
    const defaults = (window.countingOverrides && Object.keys(window.countingOverrides).length)
      ? window.countingOverrides
      : (window.countingDefaults || {});
    const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined && val !== null) el.value = val; };

    // Populate defaults/overrides
    const dir = defaults.direction_labels || {};
    setVal("labelAtoB", dir.a_to_b || "");
    setVal("labelBtoA", dir.b_to_a || "");
    const la = defaults.line_a || [];
    setVal("lineA1", la[0] ? `${la[0][0]},${la[0][1]}` : "");
    setVal("lineA2", la[1] ? `${la[1][0]},${la[1][1]}` : "");
    const lb = defaults.line_b || [];
    setVal("lineB1", lb[0] ? `${lb[0][0]},${lb[0][1]}` : "");
    setVal("lineB2", lb[1] ? `${lb[1][0]},${lb[1][1]}` : "");
    const gate = defaults.gate || {};
    setVal("gateMaxGap", gate.max_gap_frames ?? "");
    setVal("gateMinAge", gate.min_age_frames ?? "");
    setVal("gateMinDisp", gate.min_displacement_px ?? "");

    applyBtn.addEventListener("click", () => {
      status.textContent = "";
      let overrides = {};
      try {
        overrides = JSON.parse(ta.value || "{}") || {};
      } catch (e) {
        status.textContent = "Overrides must be valid JSON.";
        return;
      }
      const parsePair = (val) => {
        if (!val) return null;
        const parts = val.split(",").map((x) => parseFloat(x.trim()));
        if (parts.length !== 2 || parts.some((p) => Number.isNaN(p))) return null;
        return [parts[0], parts[1]];
      };

      const counting = overrides.counting || {};
      counting.direction_labels = {
        a_to_b: document.getElementById("labelAtoB").value || "a_to_b",
        b_to_a: document.getElementById("labelBtoA").value || "b_to_a",
      };

      const la1 = parsePair(document.getElementById("lineA1").value);
      const la2 = parsePair(document.getElementById("lineA2").value);
      const lb1 = parsePair(document.getElementById("lineB1").value);
      const lb2 = parsePair(document.getElementById("lineB2").value);
      if (la1 && la2) counting.line_a = [la1, la2];
      if (lb1 && lb2) counting.line_b = [lb1, lb2];

      counting.gate = counting.gate || {};
      const maxGap = parseInt(document.getElementById("gateMaxGap").value || "", 10);
      const minAge = parseInt(document.getElementById("gateMinAge").value || "", 10);
      const minDisp = parseFloat(document.getElementById("gateMinDisp").value || "");
      if (!Number.isNaN(maxGap)) counting.gate.max_gap_frames = maxGap;
      if (!Number.isNaN(minAge)) counting.gate.min_age_frames = minAge;
      if (!Number.isNaN(minDisp)) counting.gate.min_displacement_px = minDisp;

      overrides.counting = counting;
      ta.value = JSON.stringify(overrides, null, 2);
      status.textContent = "Applied to overrides (not saved yet).";
    });
  }
});


