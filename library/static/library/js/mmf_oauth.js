(function () {
  const panel = document.getElementById("mmf-oauth-panel");
  if (!panel) return;

  const startUrl = panel.dataset.startUrl;
  const logoutUrl = panel.dataset.logoutUrl;
  const connectedEl = document.getElementById("mmf-oauth-connected");
  const connectEl = document.getElementById("mmf-oauth-connect");
  const messageEl = document.getElementById("mmf-oauth-message");
  const usernameEl = document.getElementById("mmf-oauth-username");
  const connectBtn = document.getElementById("mmf-oauth-connect-btn");
  const logoutBtn = document.getElementById("mmf-oauth-logout-btn");
  const mmfCard = panel.closest('[data-integration-id="myminifactory"]');

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
    if (window.IntegrationsUI && mmfCard) {
      window.IntegrationsUI.setCardLoading(mmfCard, loading);
    }
  }

  function renderIntegrations(integrations) {
    if (window.IntegrationsUI) {
      window.IntegrationsUI.renderIntegrations(integrations);
    }
  }

  function showSection(section) {
    connectedEl?.classList.toggle("hidden", section !== "connected");
    connectEl?.classList.toggle("hidden", section !== "connect");
  }

  function renderStatus(status) {
    if (!status || !status.connected) {
      showSection("connect");
      if (usernameEl) usernameEl.textContent = "";
      return;
    }

    showSection("connected");
    if (usernameEl) usernameEl.textContent = status.username || "MyMiniFactory account";
    if (status.expired) {
      setMessage("Your MyMiniFactory session may have expired. Connect again if downloads fail.", "fail");
    }
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(payload || {}),
      credentials: "same-origin",
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || data.error || "Request failed");
    }
    return data;
  }

  async function startOAuth() {
    setLoading(true);
    setMessage("", null);
    try {
      const data = await postJson(startUrl, {});
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
        return;
      }
      throw new Error("MyMiniFactory did not return an authorization URL.");
    } catch (error) {
      setMessage(error.message, "fail");
      setLoading(false);
    }
  }

  async function logout() {
    setLoading(true);
    setMessage("", null);
    try {
      const data = await postJson(logoutUrl, {});
      renderStatus(data.mmf_status || { connected: false });
      if (data.integrations) renderIntegrations(data.integrations);
      setMessage(data.message || "Disconnected.", "ok");
    } catch (error) {
      setMessage(error.message, "fail");
    } finally {
      setLoading(false);
    }
  }

  function readInitialStatus() {
    const node = document.getElementById("mmf-oauth-status-data");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (_error) {
      return null;
    }
  }

  function showFlash() {
    const node = document.getElementById("integrations-flash-data");
    if (!node) return;
    let flash;
    try {
      flash = JSON.parse(node.textContent);
    } catch (_error) {
      return;
    }
    if (!flash || flash.integration !== "myminifactory" || !flash.message) return;

    setMessage(flash.message, flash.tone === "ok" ? "ok" : "fail");
    if (mmfCard) {
      const saveMessage = mmfCard.querySelector(".integration-save-message");
      if (window.IntegrationsUI?.setFeedback) {
        window.IntegrationsUI.setFeedback(
          saveMessage,
          flash.message,
          flash.tone === "ok" ? "ok" : "fail"
        );
      }
    }
  }

  renderStatus(readInitialStatus());
  showFlash();

  connectBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    startOAuth();
  });

  logoutBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    logout();
  });
})();
