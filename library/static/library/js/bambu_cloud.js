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
  const statusBody = document.getElementById("download-integrations-status");

  const regionSelect = document.getElementById("bambu-cloud-region");
  const emailInput = document.getElementById("bambu-cloud-email");
  const passwordInput = document.getElementById("bambu-cloud-password");
  const codeInput = document.getElementById("bambu-cloud-code");
  const accessTokenInput = document.getElementById("bambu-cloud-access-token");

  let verificationType = "email";

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function setMessage(text) {
    if (messageEl) messageEl.textContent = text || "";
  }

  function setLoading(loading) {
    panel.classList.toggle("about-loading", loading);
    panel.querySelectorAll("button").forEach((btn) => {
      btn.disabled = loading;
    });
  }

  function statusBadge(status) {
    if (status === "ready") return '<span class="badge badge-status saved">Ready</span>';
    if (status === "configured") return '<span class="badge badge-status downloaded">Configured</span>';
    if (status === "needs_token") return '<span class="badge badge-status saved">Needs login</span>';
    return '<span class="badge badge-status">Limited</span>';
  }

  function renderIntegrations(integrations) {
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
      setMessage("Your Bambu Cloud session may have expired. Sign in again if downloads fail.");
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
      setMessage(data.message || "Connected.");
      if (passwordInput) passwordInput.value = "";
    } catch (error) {
      setMessage(error.message);
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
      setMessage(data.message || "Connected.");
      if (codeInput) codeInput.value = "";
      if (passwordInput) passwordInput.value = "";
    } catch (error) {
      setMessage(error.message);
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
      setMessage(data.message || "Token saved.");
      if (accessTokenInput) accessTokenInput.value = "";
    } catch (error) {
      setMessage(error.message);
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
      setMessage(data.message || "Disconnected.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  document.getElementById("bambu-cloud-login-btn")?.addEventListener("click", handleLogin);
  document.getElementById("bambu-cloud-verify-btn")?.addEventListener("click", handleVerify);
  document.getElementById("bambu-cloud-token-save")?.addEventListener("click", handleTokenSave);
  document.getElementById("bambu-cloud-logout-btn")?.addEventListener("click", handleLogout);

  document.getElementById("bambu-cloud-token-toggle")?.addEventListener("click", () => {
    setMessage("");
    showSection("token");
  });
  document.getElementById("bambu-cloud-token-cancel")?.addEventListener("click", () => {
    setMessage("");
    showSection("login");
  });
  document.getElementById("bambu-cloud-verify-cancel")?.addEventListener("click", () => {
    setMessage("");
    showSection("login");
  });

  try {
    const initial = JSON.parse(panel.dataset.initialStatus || "{}");
    renderStatus(initial);
  } catch (_) {
    showSection("login");
  }
})();
