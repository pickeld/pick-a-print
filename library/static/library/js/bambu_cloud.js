(function () {
  const panel = document.getElementById("bambu-cloud-panel");
  if (!panel) return;

  const loginUrl = panel.dataset.loginUrl;
  const verifyUrl = panel.dataset.verifyUrl;
  const tokenUrl = panel.dataset.tokenUrl;
  const logoutUrl = panel.dataset.logoutUrl;

  const connectedEl = document.getElementById("bambu-cloud-connected");
  const loginEl = document.getElementById("bambu-cloud-login");
  const verifyEl = document.getElementById("bambu-cloud-verify");
  const tokenEl = document.getElementById("bambu-cloud-token");
  const messageEl = document.getElementById("bambu-cloud-message");
  const nameEl = document.getElementById("bambu-cloud-name");
  const regionBadgeEl = document.getElementById("bambu-cloud-region-badge");
  const verifyHintEl = document.getElementById("bambu-cloud-verify-hint");

  const regionSelect = document.getElementById("bambu-cloud-region");
  const emailInput = document.getElementById("bambu-cloud-email");
  const passwordInput = document.getElementById("bambu-cloud-password");
  const codeInput = document.getElementById("bambu-cloud-code");
  const accessTokenInput = document.getElementById("bambu-cloud-access-token");

  const makerworldCard = panel.closest('[data-integration-id="makerworld"]');
  let verificationType = "email";

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function setMessage(text, tone) {
    if (!messageEl) return;
    if (window.IntegrationsUI?.setFeedback) {
      window.IntegrationsUI.setFeedback(messageEl, text, tone || (text ? "info" : null));
      return;
    }
    messageEl.textContent = text || "";
  }

  function setLoading(loading) {
    panel.classList.toggle("about-loading", loading);
    panel.querySelectorAll("button").forEach((btn) => {
      btn.disabled = loading;
    });
    if (window.IntegrationsUI && makerworldCard) {
      window.IntegrationsUI.setCardLoading(makerworldCard, loading);
    }
  }

  function renderIntegrations(integrations) {
    if (window.IntegrationsUI) {
      window.IntegrationsUI.renderIntegrations(integrations);
    }
  }

  function showSection(section) {
    connectedEl.classList.toggle("hidden", section !== "connected");
    loginEl.classList.toggle("hidden", section !== "login");
    verifyEl.classList.toggle("hidden", section !== "verify");
    tokenEl.classList.toggle("hidden", section !== "token");
  }

  function renderStatus(status) {
    if (!status || !status.connected) {
      showSection("login");
      if (nameEl) nameEl.textContent = "";
      if (regionBadgeEl) regionBadgeEl.textContent = "";
      return;
    }

    showSection("connected");
    if (nameEl) nameEl.textContent = status.name || "Bambu Cloud account";
    if (regionBadgeEl) {
      regionBadgeEl.textContent = status.region === "china" ? "China" : "Global";
    }
    if (status.expired) {
      setMessage("Your Bambu Cloud session may have expired. Sign in again if downloads fail.", "fail");
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

  async function handleLogin() {
    setLoading(true);
    setMessage("");
    try {
      const data = await postJson(loginUrl, {
        email: emailInput ? emailInput.value.trim() : "",
        password: passwordInput ? passwordInput.value : "",
        region: regionSelect ? regionSelect.value : "global",
      });
      if (data.needs_verification) {
        verificationType = data.verification_type || "email";
        if (verifyHintEl) {
          verifyHintEl.textContent =
            verificationType === "totp"
              ? "Enter the 6-digit code from your authenticator app."
              : "Enter the verification code sent to your email.";
        }
        showSection("verify");
        if (codeInput) codeInput.focus();
        setMessage(data.message || "");
        return;
      }
      renderStatus(data.cloud_status);
      renderIntegrations(data.integrations);
      setMessage(data.message || "Connected.", "ok");
      if (passwordInput) passwordInput.value = "";
    } catch (error) {
      setMessage(error.message, "fail");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify() {
    setLoading(true);
    setMessage("");
    try {
      const data = await postJson(verifyUrl, {
        code: codeInput ? codeInput.value.trim() : "",
      });
      renderStatus(data.cloud_status);
      renderIntegrations(data.integrations);
      setMessage(data.message || "Connected.", "ok");
      if (codeInput) codeInput.value = "";
      if (passwordInput) passwordInput.value = "";
    } catch (error) {
      setMessage(error.message, "fail");
    } finally {
      setLoading(false);
    }
  }

  async function handleTokenSave() {
    setLoading(true);
    setMessage("");
    try {
      const data = await postJson(tokenUrl, {
        access_token: accessTokenInput ? accessTokenInput.value.trim() : "",
        region: regionSelect ? regionSelect.value : "global",
      });
      renderStatus(data.cloud_status);
      renderIntegrations(data.integrations);
      setMessage(data.message || "Token saved.", "ok");
      if (accessTokenInput) accessTokenInput.value = "";
    } catch (error) {
      setMessage(error.message, "fail");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    setLoading(true);
    setMessage("");
    try {
      const data = await postJson(logoutUrl, {});
      renderStatus(data.cloud_status);
      renderIntegrations(data.integrations);
      setMessage(data.message || "Disconnected.", "info");
    } catch (error) {
      setMessage(error.message, "fail");
    } finally {
      setLoading(false);
    }
  }

  document.getElementById("bambu-cloud-login-btn")?.addEventListener("click", (event) => {
    event.stopPropagation();
    handleLogin();
  });
  document.getElementById("bambu-cloud-verify-btn")?.addEventListener("click", (event) => {
    event.stopPropagation();
    handleVerify();
  });
  document.getElementById("bambu-cloud-token-save")?.addEventListener("click", (event) => {
    event.stopPropagation();
    handleTokenSave();
  });
  document.getElementById("bambu-cloud-logout-btn")?.addEventListener("click", (event) => {
    event.stopPropagation();
    handleLogout();
  });

  document.getElementById("bambu-cloud-token-toggle")?.addEventListener("click", (event) => {
    event.stopPropagation();
    setMessage("");
    showSection("token");
  });
  document.getElementById("bambu-cloud-token-cancel")?.addEventListener("click", (event) => {
    event.stopPropagation();
    setMessage("");
    showSection("login");
  });
  document.getElementById("bambu-cloud-verify-cancel")?.addEventListener("click", (event) => {
    event.stopPropagation();
    setMessage("");
    showSection("login");
  });

  try {
    const statusEl = document.getElementById("bambu-cloud-status-data");
    const initial = statusEl ? JSON.parse(statusEl.textContent) : {};
    renderStatus(initial);
  } catch (_) {
    showSection("login");
  }
})();
