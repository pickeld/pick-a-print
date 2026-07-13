(function () {
  const modelViewer = document.getElementById("model-preview-viewer");
  const viewerLoading = document.getElementById("model-preview-loading");
  const viewerError = document.getElementById("model-preview-error");
  const previewSection = document.getElementById("model-preview-section");
  const thumbButtons = document.querySelectorAll(".model-file-thumb");
  if (!modelViewer || !viewerLoading) return;

  const viewer = window.PickAPrintViewer?.bind(modelViewer, viewerLoading, viewerError, {
    errorMessage: "Could not load the 3D preview. Try downloading the STL and re-uploading.",
  });

  let activeFileId = previewSection?.dataset.activeFileId || null;

  function setActiveThumb(fileId) {
    activeFileId = fileId;
    if (previewSection) previewSection.dataset.activeFileId = fileId;
    thumbButtons.forEach((button) => {
      const isActive = button.dataset.fileId === fileId;
      button.classList.toggle("model-file-thumb--active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });
  }

  thumbButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const fileId = button.dataset.fileId;
      const previewUrl = button.dataset.previewUrl;
      if (!fileId || !previewUrl || fileId === activeFileId) return;

      setActiveThumb(fileId);
      viewer?.showLoading();
      modelViewer.src = previewUrl;
    });
  });

  window.customElements?.whenDefined("model-viewer").then(() => {
    if (modelViewer.loaded) viewer?.hideLoading();
  });
})();
