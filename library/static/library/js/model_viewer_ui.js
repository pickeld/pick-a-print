(function () {
  function formatPercent(progress) {
    return `${Math.min(100, Math.round((progress || 0) * 100))}%`;
  }

  function bindModelViewerProgress(modelViewer, loadingRoot, errorEl, options) {
    if (!modelViewer || !loadingRoot) return null;

    const opts = options || {};
    const errorMessage = opts.errorMessage || "Could not load the 3D preview.";

    const bar = loadingRoot.querySelector(".viewer-load-bar");
    const percentEl = loadingRoot.querySelector(".viewer-load-percent");
    const labelEl = loadingRoot.querySelector(".viewer-load-label");

    function setProgress(progress) {
      const pct = formatPercent(progress);
      if (bar) bar.style.width = pct;
      if (percentEl) percentEl.textContent = pct;
      if (labelEl) {
        labelEl.textContent = progress > 0 && progress < 1 ? "Loading 3D model" : "Preparing preview";
      }
    }

    function showLoading() {
      setProgress(0);
      loadingRoot.classList.remove("hidden");
      if (errorEl) errorEl.classList.add("hidden");
      modelViewer.classList.remove("hidden");
    }

    function hideLoading() {
      setProgress(1);
      loadingRoot.classList.add("hidden");
    }

    function showError(message) {
      hideLoading();
      if (errorEl) {
        errorEl.textContent = message || errorMessage;
        errorEl.classList.remove("hidden");
      }
      modelViewer.classList.add("hidden");
    }

    modelViewer.addEventListener("progress", (event) => {
      setProgress(event.detail?.totalProgress ?? 0);
    });

    modelViewer.addEventListener("load", () => {
      hideLoading();
      if (errorEl) errorEl.classList.add("hidden");
      modelViewer.classList.remove("hidden");
    });

    modelViewer.addEventListener("error", () => {
      showError(errorMessage);
    });

    return { showLoading, hideLoading, showError, setProgress };
  }

  window.PickAPrintViewer = { bind: bindModelViewerProgress };
})();
