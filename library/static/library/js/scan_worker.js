(function () {
  const panel = document.getElementById("scan-worker-panel");
  if (!panel) return;

  const checksUrl = panel.dataset.checksUrl;
  const saveUrl = panel.dataset.saveUrl;
  const testBtn = document.getElementById("scan-worker-test-btn");
  const saveBtn = document.getElementById("scan-worker-save-btn");
  const statusEl = document.getElementById("scan-worker-status");
  const hostInput = document.getElementById("jetson-host");
  const portInput = document.getElementById("jetson-health-port");
  const tokenInput = document.getElementById("jetson-health-token");
  const enabledInput = document.getElementById("jetson-enabled");

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function setLoading(loading) {
    panel.classList.toggle("about-loading", loading);
    if (testBtn) testBtn.disabled = loading;
    if (saveBtn) saveBtn.disabled = loading;
  }

  function renderStatus(data) {
    if (!statusEl) return;
    const ready = Boolean(data.ready || data.last_test_ok);
    const badgeClass = ready ? "badge-dep-ok" : "badge-dep-warn";
    const badgeText = ready ? "Ready" : "Not ready";
    const workers = typeof data.celery_workers === "number" ? data.celery_workers : "—";
    const hostReachable = data.host_reachable ? "yes" : "no";
    statusEl.innerHTML = `
      <div class="scan-worker-status-grid">
        <div><span class="badge badge-dep ${badgeClass}">${badgeText}</span></div>
        <div class="text-muted">${data.message || data.last_test_message || "No connection test run yet."}</div>
        <div class="helptext">Host reachable: ${hostReachable} · Scan workers on Redis: ${workers}</div>
      </div>`;
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(payload),
      credentials: "same-origin",
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || data.error || "Request failed");
    }
    return data;
  }

  function buildPayload() {
    const payload = {
      jetson_host: hostInput ? hostInput.value : "",
      jetson_health_port: portInput ? Number(portInput.value || 8765) : 8765,
      jetson_enabled: enabledInput ? enabledInput.checked : false,
    };
    if (tokenInput && tokenInput.value.trim()) {
      payload.jetson_health_token = tokenInput.value.trim();
    }
    return payload;
  }

  async function runTest() {
    setLoading(true);
    try {
      const data = await postJson(checksUrl, buildPayload());
      renderStatus(data);
    } catch (error) {
      if (statusEl) {
        statusEl.innerHTML = `<div class="text-muted">${error.message}</div>`;
      }
    } finally {
      setLoading(false);
    }
  }

  async function saveSettings() {
    setLoading(true);
    try {
      const data = await postJson(saveUrl, buildPayload());
      if (tokenInput) {
        tokenInput.value = "";
        tokenInput.placeholder = "•••••••• (saved)";
      }
      renderStatus(data);
    } catch (error) {
      if (statusEl) {
        statusEl.innerHTML = `<div class="text-muted">${error.message}</div>`;
      }
    } finally {
      setLoading(false);
    }
  }

  if (testBtn) {
    testBtn.addEventListener("click", runTest);
  }
  if (saveBtn) {
    saveBtn.addEventListener("click", saveSettings);
  }

  const initial = panel.dataset.initialStatus;
  if (initial) {
    try {
      renderStatus(JSON.parse(initial));
    } catch (_error) {
      /* ignore malformed bootstrap payload */
    }
  }
})();
