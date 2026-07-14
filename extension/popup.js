const apiBase = document.getElementById("apiBase");
const apiToken = document.getElementById("apiToken");
const status = document.getElementById("status");
const saveTabBtn = document.getElementById("saveTab");
const settingsLink = document.getElementById("settingsLink");

function setStatus(text, kind) {
  status.textContent = text;
  status.className = "status" + (kind ? " " + kind : "");
}

function settingsPageUrl(base) {
  return `${base.replace(/\/api\/?$/, "").replace(/\/$/, "")}/settings/?tab=api`;
}

async function loadBundledDefaults() {
  try {
    const res = await fetch(chrome.runtime.getURL("defaults.json"));
    if (!res.ok) return {};
    return await res.json();
  } catch (_) {
    return {};
  }
}

async function initPopup() {
  const stored = await chrome.storage.sync.get(["apiBase", "apiToken"]);
  const defaults = await loadBundledDefaults();
  const base = stored.apiBase || defaults.apiBase || "";
  const token = stored.apiToken || defaults.apiToken || "";

  apiBase.value = base;
  apiToken.value = token;
  if (base) settingsLink.href = settingsPageUrl(base);
}

initPopup();

document.getElementById("saveSettings").addEventListener("click", () => {
  chrome.storage.sync.set(
    { apiBase: apiBase.value.trim(), apiToken: apiToken.value.trim() },
    () => {
      setStatus("Settings saved!", "ok");
      if (apiBase.value.trim()) {
        settingsLink.href = settingsPageUrl(apiBase.value.trim());
      }
      setTimeout(() => setStatus(""), 2000);
    }
  );
});

saveTabBtn.addEventListener("click", async () => {
  saveTabBtn.disabled = true;
  setStatus("Saving...", "");
  try {
    const res = await chrome.runtime.sendMessage({ type: "SAVE_CURRENT_TAB" });
    if (res.ok) {
      const label = res.created ? "Saved" : "Updated";
      setStatus(`${label}: ${res.title || "model"}`, "ok");
    } else {
      setStatus(res.error || "Failed", "err");
    }
  } catch (e) {
    setStatus("Extension error — reload extension", "err");
  }
  saveTabBtn.disabled = false;
});
