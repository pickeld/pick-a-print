async function applyBundledDefaults() {
  const { apiBase, apiToken } = await chrome.storage.sync.get(["apiBase", "apiToken"]);
  if (apiBase && apiToken) return;

  try {
    const res = await fetch(chrome.runtime.getURL("defaults.json"));
    if (!res.ok) return;
    const defaults = await res.json();
    const patch = {};
    if (!apiBase && defaults.apiBase) patch.apiBase = defaults.apiBase;
    if (!apiToken && defaults.apiToken) patch.apiToken = defaults.apiToken;
    if (Object.keys(patch).length) {
      await chrome.storage.sync.set(patch);
    }
  } catch (_) {
    /* no bundled defaults (dev load unpacked without download) */
  }
}

chrome.runtime.onInstalled.addListener(() => {
  applyBundledDefaults();
});

applyBundledDefaults();

async function saveModelUrl(url) {
  const { apiBase, apiToken } = await chrome.storage.sync.get(["apiBase", "apiToken"]);
  if (!apiBase || !apiToken) {
    return { ok: false, error: "Set API URL & token in extension popup" };
  }

  const base = apiBase.replace(/\/$/, "");
  try {
    const res = await fetch(`${base}/models/save/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Token ${apiToken}`,
      },
      body: JSON.stringify({ url }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { ok: false, error: data.detail || data.url?.[0] || `HTTP ${res.status}` };
    }
    return { ok: true, created: res.status === 201, title: data.title };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "SAVE_URL") {
    saveModelUrl(message.url).then(sendResponse);
    return true;
  }

  if (message.type === "SAVE_CURRENT_TAB") {
    (async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.url) {
        sendResponse({ ok: false, error: "No active tab" });
        return;
      }
      if (!/^https?:\/\//i.test(tab.url)) {
        sendResponse({ ok: false, error: "This page cannot be saved (not a web URL)" });
        return;
      }
      sendResponse(await saveModelUrl(tab.url));
    })();
    return true;
  }
});
