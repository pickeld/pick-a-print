(function () {
  document.querySelectorAll(".part-card-preview model-viewer").forEach((viewer) => {
    const wrap = viewer.closest(".part-card-preview");
    const loading = wrap?.querySelector(".part-card-loading");
    const errorEl = wrap?.querySelector(".part-card-error");
    if (!loading) return;

    const bar = loading.querySelector(".viewer-load-bar");

    function hideLoading() {
      loading.classList.add("hidden");
    }

    function showError() {
      hideLoading();
      errorEl?.classList.remove("hidden");
      viewer.classList.add("hidden");
    }

    viewer.addEventListener("progress", (event) => {
      const progress = event.detail?.totalProgress ?? 0;
      if (bar) bar.style.width = `${Math.min(100, Math.round(progress * 100))}%`;
    });

    viewer.addEventListener("load", hideLoading);
    viewer.addEventListener("error", showError);

    window.customElements?.whenDefined("model-viewer").then(() => {
      if (viewer.loaded) hideLoading();
    });
  });
})();
