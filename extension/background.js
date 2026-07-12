chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== "SAVE_URL") return;

  (async () => {
    const { apiBase, apiToken } = await chrome.storage.sync.get(["apiBase", "apiToken"]);
    if (!apiBase || !apiToken) {
      sendResponse({ ok: false, error: "Set API URL & token in extension popup" });
      return;
    }

    const base = apiBase.replace(/\/$/, "");
    try {
      const res = await fetch(`${base}/models/save/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Token ${apiToken}`,
        },
        body: JSON.stringify({ url: message.url }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        sendResponse({ ok: false, error: data.detail || `HTTP ${res.status}` });
        return;
      }
      sendResponse({ ok: true, created: res.status === 201, title: data.title });
    } catch (e) {
      sendResponse({ ok: false, error: String(e) });
    }
  })();

  return true;
});
