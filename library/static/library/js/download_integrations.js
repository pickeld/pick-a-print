(function () {
  const panel = document.getElementById("download-integrations-panel");
  if (!panel) return;

  const saveUrl = panel.dataset.saveUrl;
  const saveBtn = document.getElementById("download-integrations-save-btn");
  const statusBody = document.getElementById("download-integrations-status");
  const messageEl = document.getElementById("download-integrations-message");
  const makerworldInput = document.getElementById("bambu-lab-token");
  const thingiverseInput = document.getElementById("thingiverse-api-token");
  const myminifactoryInput = document.getElementById("myminifactory-api-key");

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function statusBadge(status) {
    if (status === "ready") {
      return '<span class="badge badge-status saved">Ready</span>';
    }
    if (status === "configured") {
      return '<span class="badge badge-status downloaded">Configured</span>';
    }
    if (status === "needs_token") {
      return '<span class="badge badge-status saved">Needs token</span>';
    }
    return '<span class="badge badge-status">Limited</span>';
  }

  function renderStatus(integrations) {
    if (!statusBody || !Array.isArray(integrations)) return;
    statusBody.innerHTML = integrations
      .map(
        (row) => `
        <tr>
          <td>${row.site}</td>
          <td>${statusBadge(row.status)}</td>
          <td class="text-muted">${row.note || ""}</td>
        </tr>`
      )
      .join("");
  }

  function setLoading(loading) {
    panel.classList.toggle("about-loading", loading);
    if (saveBtn) saveBtn.disabled = loading;
  }

  function clearSavedPlaceholders(saved) {
    const fields = [
      [makerworldInput, "bambu_lab_token"],
      [thingiverseInput, "thingiverse_api_token"],
      [myminifactoryInput, "myminifactory_api_key"],
    ];
    for (const [input, key] of fields) {
      if (!input || !saved || !saved[key]) continue;
      input.value = "";
      input.placeholder = "•••••••• (saved)";
    }
  }

  function buildPayload() {
    const payload = {};
    if (makerworldInput && makerworldInput.value.trim()) {
      payload.bambu_lab_token = makerworldInput.value.trim();
    }
    if (thingiverseInput && thingiverseInput.value.trim()) {
      payload.thingiverse_api_token = thingiverseInput.value.trim();
    }
    if (myminifactoryInput && myminifactoryInput.value.trim()) {
      payload.myminifactory_api_key = myminifactoryInput.value.trim();
    }
    return payload;
  }

  async function saveSettings() {
    setLoading(true);
    if (messageEl) messageEl.textContent = "";
    try {
      const response = await fetch(saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(buildPayload()),
        credentials: "same-origin",
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || data.error || "Request failed");
      }
      renderStatus(data.integrations);
      clearSavedPlaceholders(data.saved);
      if (messageEl) messageEl.textContent = data.message || "Saved.";
    } catch (error) {
      if (messageEl) messageEl.textContent = error.message;
    } finally {
      setLoading(false);
    }
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", saveSettings);
  }
})();
