(function () {
  const panel = document.getElementById("integrations-panel");
  if (!panel) return;

  const testUrl = panel.dataset.testUrl;
  const saveUrl = panel.dataset.saveUrl;
  const overviewActive = document.getElementById("integrations-overview-active");
  const overviewSetup = document.getElementById("integrations-overview-setup");
  const overviewProgress = document.getElementById("integrations-overview-progress");
  const cards = () => Array.from(panel.querySelectorAll(".integration-card"));

  const STATUS_META = {
    ready: { label: "Active", icon: "mdi-check-circle" },
    configured: { label: "Connected", icon: "mdi-link-variant" },
    needs_token: { label: "Setup", icon: "mdi-alert-circle-outline" },
    unsupported: { label: "Metadata", icon: "mdi-information-outline" },
  };

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function statusPill(status) {
    const meta = STATUS_META[status] || { label: "Limited", icon: "mdi-help-circle-outline" };
    return `<span class="integration-status-pill integration-status-pill--${status}"><span class="mdi ${meta.icon}" aria-hidden="true"></span>${meta.label}</span>`;
  }

  function summarize(integrations) {
    const total = integrations.length;
    const active = integrations.filter((row) => ["ready", "configured"].includes(row.status)).length;
    const setup = integrations.filter((row) => row.status === "needs_token").length;
    const percent = total ? Math.round((active / total) * 100) : 0;
    return { active, setup, total, percent };
  }

  function updateOverview(integrations) {
    const stats = summarize(integrations);
    if (overviewActive) overviewActive.textContent = String(stats.active);
    if (overviewSetup) overviewSetup.textContent = String(stats.setup);
    if (overviewProgress) overviewProgress.style.width = `${stats.percent}%`;
  }

  function setCardLoading(card, loading) {
    if (!card) return;
    card.classList.toggle("integration-loading", loading);
    card.querySelectorAll("button").forEach((btn) => {
      btn.disabled = loading;
    });
  }

  function setTestLoading(card, loading) {
    const btn = card?.querySelector(".integration-test-btn");
    if (!btn) return;
    btn.classList.toggle("is-loading", loading);
    const icon = btn.querySelector(".integration-test-icon");
    if (!icon) return;
    icon.classList.toggle("mdi-lan-connect", !loading);
    icon.classList.toggle("mdi-loading", loading);
  }

  function setFeedback(el, message, tone) {
    if (!el) return;
    el.textContent = message || "";
    el.classList.remove("integration-feedback-ok", "integration-feedback-fail", "integration-feedback-info", "integration-test-ok", "integration-test-fail");
    if (!message) return;
    if (tone === "ok") {
      el.classList.add(el.classList.contains("integration-test-result") ? "integration-test-ok" : "integration-feedback-ok");
    } else if (tone === "fail") {
      el.classList.add(el.classList.contains("integration-test-result") ? "integration-test-fail" : "integration-feedback-fail");
    } else {
      el.classList.add("integration-feedback-info");
    }
  }

  function setTestResult(card, message, ok) {
    const resultEl = card?.querySelector(".integration-test-result");
    if (!message) {
      setFeedback(resultEl, "", null);
      return;
    }
    setFeedback(resultEl, message, ok ? "ok" : "fail");
  }

  function renderIntegrations(integrations) {
    if (!Array.isArray(integrations)) return;
    integrations.forEach((row) => {
      const card = panel.querySelector(`[data-integration-id="${row.id}"]`);
      if (!card) return;
      card.dataset.status = row.status;
      const badge = card.querySelector(".integration-status-badge");
      if (badge) badge.innerHTML = statusPill(row.status);
      const note = card.querySelector(".integration-summary-text");
      if (note) note.textContent = row.note || "";
    });
    updateOverview(integrations);
  }

  window.IntegrationsUI = {
    renderIntegrations,
    statusPill,
    setTestResult,
    setCardLoading,
    setFeedback,
  };

  cards().forEach((card) => {
    card.addEventListener("toggle", () => {
      if (!card.open) return;
      cards().forEach((other) => {
        if (other !== card) other.open = false;
      });
    });
  });

  function buildCredentialPayload(card) {
    const payload = {};
    const thingiverseInput = card.querySelector('[name="thingiverse_api_token"]');
    const makerworldInput = card.querySelector('[name="bambu_lab_token"]');
    if (thingiverseInput?.value.trim()) {
      payload.thingiverse_api_token = thingiverseInput.value.trim();
    }
    if (makerworldInput?.value.trim()) {
      payload.bambu_lab_token = makerworldInput.value.trim();
    }
    return payload;
  }

  function clearSavedPlaceholders(card, saved) {
    const fields = [
      ['[name="bambu_lab_token"]', "bambu_lab_token"],
      ['[name="thingiverse_api_token"]', "thingiverse_api_token"],
    ];
    for (const [selector, key] of fields) {
      const input = card.querySelector(selector);
      if (!input || !saved?.[key]) continue;
      input.value = "";
      input.placeholder = "Saved — leave blank to keep";
    }
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

  async function runTest(card, integrationId) {
    setCardLoading(card, true);
    setTestLoading(card, true);
    setTestResult(card, "Testing connection…", null);
    try {
      const payload = { integration: integrationId, ...buildCredentialPayload(card) };
      const response = await fetch(testUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
        credentials: "same-origin",
      });
      const data = await response.json();
      if (data.integrations) renderIntegrations(data.integrations);
      setTestResult(card, data.message || (data.ok ? "Connection successful." : "Test failed."), data.ok);
    } catch (error) {
      setTestResult(card, error.message, false);
    } finally {
      setCardLoading(card, false);
      setTestLoading(card, false);
    }
  }

  async function saveCredentials(card) {
    setCardLoading(card, true);
    const messageEl = card.querySelector(".integration-save-message");
    setFeedback(messageEl, "", null);
    try {
      const data = await postJson(saveUrl, buildCredentialPayload(card));
      renderIntegrations(data.integrations);
      clearSavedPlaceholders(card, data.saved);
      setFeedback(messageEl, data.message || "Saved.", "ok");
      setTestResult(card, "", null);
    } catch (error) {
      setFeedback(messageEl, error.message, "fail");
    } finally {
      setCardLoading(card, false);
    }
  }

  panel.addEventListener("click", (event) => {
    const testBtn = event.target.closest("[data-integration-test]");
    if (testBtn) {
      event.preventDefault();
      event.stopPropagation();
      const card = testBtn.closest(".integration-card");
      const integrationId = testBtn.dataset.integrationTest;
      if (card && integrationId) runTest(card, integrationId);
      return;
    }

    const saveBtn = event.target.closest("[data-integration-save]");
    if (saveBtn) {
      event.preventDefault();
      event.stopPropagation();
      const card = saveBtn.closest(".integration-card");
      if (card) saveCredentials(card);
    }
  });
})();
