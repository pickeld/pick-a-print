const apiBase = document.getElementById("apiBase");
const apiToken = document.getElementById("apiToken");
const status = document.getElementById("status");

chrome.storage.sync.get(["apiBase", "apiToken"], (data) => {
  if (data.apiBase) apiBase.value = data.apiBase;
  if (data.apiToken) apiToken.value = data.apiToken;
});

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.sync.set(
    { apiBase: apiBase.value.trim(), apiToken: apiToken.value.trim() },
    () => {
      status.textContent = "Saved!";
      setTimeout(() => (status.textContent = ""), 2000);
    }
  );
});
