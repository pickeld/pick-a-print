(function () {
  const modelViewer = document.getElementById("model-preview-viewer");
  const viewerLoading = document.getElementById("model-preview-loading");
  const viewerError = document.getElementById("model-preview-error");
  const previewSection = document.getElementById("model-preview-section");
  const thumbStrip = document.getElementById("model-file-thumbs");
  if (!modelViewer || !viewerLoading) return;

  const viewer = window.PickAPrintViewer?.bind(modelViewer, viewerLoading, viewerError, {
    errorMessage: "Could not load the 3D preview. Try downloading the STL and re-uploading.",
  });

  let activeFileId = previewSection?.dataset.activeFileId || null;

  function setActiveThumb(fileId) {
    activeFileId = String(fileId);
    if (previewSection) previewSection.dataset.activeFileId = activeFileId;

    thumbStrip?.querySelectorAll(".model-file-thumb").forEach((thumb) => {
      const isActive = thumb.dataset.fileId === activeFileId;
      thumb.classList.toggle("model-file-thumb--active", isActive);
      thumb.setAttribute("aria-selected", isActive ? "true" : "false");
    });
  }

  function switchPreview(fileId, previewUrl) {
    if (!fileId || !previewUrl || String(fileId) === String(activeFileId)) return;

    setActiveThumb(fileId);
    viewer?.showLoading();

    window.customElements.whenDefined("model-viewer").then(() => {
      modelViewer.setAttribute("src", previewUrl);
      if (typeof modelViewer.dismissPoster === "function") {
        modelViewer.dismissPoster();
      }
      modelViewer.cameraOrbit = "auto auto auto";
    });
  }

  function handleThumbActivate(thumb) {
    switchPreview(thumb.dataset.fileId, thumb.dataset.previewUrl);
  }

  thumbStrip?.addEventListener("click", (event) => {
    const thumb = event.target.closest(".model-file-thumb");
    if (!thumb || !thumbStrip.contains(thumb)) return;
    handleThumbActivate(thumb);
  });

  thumbStrip?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const thumb = event.target.closest(".model-file-thumb");
    if (!thumb || !thumbStrip.contains(thumb)) return;
    event.preventDefault();
    handleThumbActivate(thumb);
  });

  window.customElements.whenDefined("model-viewer").then(() => {
    if (modelViewer.loaded) viewer?.hideLoading();
  });
})();
