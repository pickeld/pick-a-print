(function () {
  if (document.getElementById("tdl-save-btn")) return;

  const btn = document.createElement("button");
  btn.id = "tdl-save-btn";
  btn.type = "button";
  btn.textContent = "Save to Library";
  btn.title = "Save this model to Pick-a-Print";

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
      const res = await chrome.runtime.sendMessage({ type: "SAVE_URL", url: window.location.href });
      if (res.ok) {
        btn.textContent = res.created ? "Saved ✓" : "Updated ✓";
        btn.classList.add("success");
      } else {
        btn.textContent = res.error || "Failed";
        btn.classList.add("error");
      }
    } catch (e) {
      btn.textContent = "Configure extension";
      btn.classList.add("error");
    }
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = "Save to Library";
      btn.classList.remove("success", "error");
    }, 2500);
  });

  document.body.appendChild(btn);
})();
