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
  const viewerSection = document.getElementById("scan-viewer-section");
  const previewWarning = document.getElementById("scan-preview-warning");
  const modelViewer = document.getElementById("scan-model-viewer");
  const viewerLoading = document.getElementById("scan-viewer-loading");
  const viewerError = document.getElementById("scan-viewer-error");

  let polling = !document.getElementById("scan-stage-badge")?.textContent?.match(/COMPLETED|FAILED/);

  function downloadUrl(filename, inline) {
    const url = downloadBase.replace("__FILE__", encodeURIComponent(filename));
    return inline ? `${url}?inline=1` : url;
  }

  function updateSteps(steps) {
    if (!stepsEl || !steps) return;
    steps.forEach((step) => {
      const li = stepsEl.querySelector(`[data-step="${step.key}"]`);
      if (!li) return;
      li.className = `scan-step scan-step--${step.state}`;
    });
  }

  function hideViewerLoading() {
    if (viewerLoading) viewerLoading.classList.add("hidden");
  }

  function showViewerError(message) {
    hideViewerLoading();
    if (viewerError) {
      viewerError.textContent = message;
      viewerError.classList.remove("hidden");
    }
    if (modelViewer) modelViewer.classList.add("hidden");
  }

  function bindViewerEvents() {
    if (!modelViewer) return;
    modelViewer.addEventListener("load", () => {
      hideViewerLoading();
      if (viewerError) viewerError.classList.add("hidden");
      modelViewer.classList.remove("hidden");
    });
    modelViewer.addEventListener("error", () => {
      showViewerError("Could not load the 3D preview. The GLB file may be invalid — try re-running the scan.");
    });
    if (modelViewer.loaded) {
      hideViewerLoading();
    }
  }

  function updateViewer(viewerFile) {
    if (!viewerSection || !modelViewer || !viewerFile) return;
    const src = downloadUrl(viewerFile, true);
    if (modelViewer.getAttribute("src") !== src) {
      if (viewerLoading) viewerLoading.classList.remove("hidden");
      if (viewerError) viewerError.classList.add("hidden");
      modelViewer.classList.remove("hidden");
      modelViewer.setAttribute("src", src);
    }
    viewerSection.classList.remove("hidden");
  }

  function updatePreviewWarnings(preview) {
    if (!previewWarning) return;
    const warnings = preview?.warnings || [];
    if (!warnings.length) {
      previewWarning.classList.add("hidden");
      previewWarning.innerHTML = "";
      return;
    }
    previewWarning.classList.remove("hidden");
    previewWarning.innerHTML = warnings.map((w) => `<p>${w}</p>`).join("");
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
      a.href = downloadUrl(filename, false);
      a.className = "btn btn-secondary btn-sm";
      a.textContent = `Download ${key.toUpperCase()}`;
      outputLinks.appendChild(a);
    });

    if (data.viewer_file) {
      updateViewer(data.viewer_file);
    }
    updatePreviewWarnings(data.preview);

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

  bindViewerEvents();

  const initialPreviewEl = document.getElementById("scan-initial-preview");
  if (initialPreviewEl) {
    try {
      updatePreviewWarnings(JSON.parse(initialPreviewEl.textContent));
    } catch (err) {
      console.warn("Could not parse initial preview status", err);
    }
  }

  if (polling) {
    poll();
  } else if (modelViewer?.getAttribute("src")) {
    // Already completed — model-viewer may have loaded before listeners attached
    window.customElements?.whenDefined("model-viewer").then(() => {
      if (modelViewer.loaded) hideViewerLoading();
    });
  }
})();
