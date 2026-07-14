(function () {
  const statusEl = document.getElementById("mmf-oauth-status");
  if (!statusEl) return;

  function fail(message) {
    statusEl.textContent = message;
  }

  function succeed(message) {
    statusEl.textContent = message;
  }

  const configNode = document.getElementById("mmf-oauth-config-data");
  if (!configNode) {
    fail("Could not load OAuth settings. Return to Settings and try again.");
    return;
  }

  let config;
  try {
    config = JSON.parse(configNode.textContent);
  } catch (_error) {
    fail("Could not load OAuth settings. Return to Settings and try again.");
    return;
  }

  const completeUrl = config.complete_url;
  const settingsUrl = config.settings_url;
  const expectedState = config.expected_state || "";

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function parseParams(searchOrHash) {
    const raw = (searchOrHash || "").replace(/^[?#]/, "");
    return raw ? new URLSearchParams(raw) : new URLSearchParams();
  }

  succeed("Finishing sign-in…");

  const hashParams = parseParams(window.__mmfOAuthHash || window.location.hash);
  const queryParams = parseParams(window.__mmfOAuthSearch || window.location.search);

  const error = hashParams.get("error") || queryParams.get("error");
  if (error) {
    const description = hashParams.get("error_description") || queryParams.get("error_description") || error;
    fail("MyMiniFactory sign-in was cancelled or failed: " + description);
    return;
  }

  const accessToken =
    hashParams.get("access_token") ||
    queryParams.get("access_token") ||
    "";
  const state = hashParams.get("state") || queryParams.get("state") || "";
  const expiresIn = Number(hashParams.get("expires_in") || queryParams.get("expires_in") || "0");

  if (!accessToken) {
    if (queryParams.get("code")) {
      fail(
        "MyMiniFactory returned an authorization code, but the token step did not finish on the server. " +
          "Return to Settings and click Connect again."
      );
      return;
    }
    fail("No access token returned from MyMiniFactory. Try connecting again from Settings.");
    return;
  }

  if (!expectedState || state !== expectedState) {
    fail("OAuth state mismatch. Please start the connection again from Settings.");
    return;
  }

  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    fail("Missing security token. Reload this page or start Connect again from Settings.");
    return;
  }

  succeed("Saving MyMiniFactory connection…");

  fetch(completeUrl, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({
      access_token: accessToken,
      expires_in: expiresIn,
      state: state,
    }),
  })
    .then(function (response) {
      return response.text().then(function (text) {
        let data = {};
        if (text) {
          try {
            data = JSON.parse(text);
          } catch (_error) {
            throw new Error("Unexpected server response while saving MyMiniFactory connection.");
          }
        }
        if (!response.ok) {
          throw new Error(data.error || data.message || "Could not save MyMiniFactory connection.");
        }
        return data;
      });
    })
    .then(function (data) {
      window.location.replace(data.redirect || settingsUrl);
    })
    .catch(function (err) {
      fail(err.message || "Could not complete MyMiniFactory sign-in.");
    });
})();
