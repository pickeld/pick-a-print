(function () {
  const root = document.getElementById("scan-job");
  if (!root) return;

  const statusUrl = root.dataset.statusUrl;
  const downloadBase = root.dataset.downloadBase;
  const progressBar = document.getElementById("scan-progress-bar");
  const progressText = document.getElementById("scan-progress-text");
  const stageBadge = document.getElementById("scan-stage-badge");
  const stepsEl = document.getElementById("scan-steps");
  const logPanel = document.getElementById("scan-log-panel");
  const logCount = document.getElementById("scan-log-count");
  const errorEl = document.getElementById("scan-error");
  const outputsEl = document.getElementById("scan-outputs");
  const outputLinks = document.getElementById("scan-output-links");
  const importBtn = document.getElementById("scan-import-btn");
  const importNote = document.getElementById("scan-import-note");

  let polling = true;

  function downloadUrl(filename) {
    return downloadBase.replace("__FILE__", encodeURIComponent(filename));
  }

  function updateSteps(steps) {
    if (!stepsEl || !steps) return;
    steps.forEach((step) => {
      const li = stepsEl.querySelector(`[data-step="${step.key}"]`);
      if (!li) return;
      li.className = `scan-step scan-step--${step.state}`;
    });
  }

  function updateOutputs(data) {
    if (!outputsEl || !outputLinks) return;
    if (!data.completed || !data.outputs || Object.keys(data.outputs).length === 0) {
      outputsEl.classList.add("hidden");
      return;
    }

    outputsEl.classList.remove("hidden");
    outputLinks.innerHTML = "";
    Object.entries(data.outputs).forEach(([key, filename]) => {
      const a = document.createElement("a");
      a.href = downloadUrl(filename);
      a.className = "btn btn-secondary btn-sm";
      a.textContent = `Download ${key.toUpperCase()}`;
      outputLinks.appendChild(a);
    });

    if (data.saved_model_id) {
      importBtn.disabled = true;
      importBtn.textContent = "Already in Library";
      importNote.textContent = "This scan was saved to your library.";
    } else {
      importBtn.disabled = false;
      importBtn.textContent = "Save STL to Library";
      importNote.textContent = "";
    }
  }

  function renderStatus(data) {
    if (progressBar) progressBar.style.width = `${data.progress || 0}%`;
    if (progressText) progressText.textContent = `${data.progress || 0}%`;
    if (stageBadge) {
      stageBadge.textContent = data.stage;
      stageBadge.className = `badge scan-badge scan-badge--${(data.stage || "").toLowerCase()}`;
    }

    updateSteps(data.steps);

    if (errorEl) {
      if (data.error) {
        errorEl.textContent = data.error;
        errorEl.classList.remove("hidden");
      } else {
        errorEl.classList.add("hidden");
      }
    }

    if (logPanel && Array.isArray(data.log_lines)) {
      logPanel.textContent = data.log_lines.join("\n");
      logPanel.scrollTop = logPanel.scrollHeight;
      if (logCount) logCount.textContent = `${data.log_lines.length} lines`;
    }

    updateOutputs(data);

    if (data.completed || data.failed) {
      polling = false;
    }
  }

  async function poll() {
    if (!polling) return;
    try {
      const res = await fetch(statusUrl, { headers: { Accept: "application/json" } });
      if (res.ok) {
        const data = await res.json();
        renderStatus(data);
      }
    } catch (err) {
      console.error("Scan status poll failed", err);
    }
    if (polling) {
      window.setTimeout(poll, 2000);
    }
  }

  poll();
})();
