(function () {
  const modelViewer = document.getElementById("model-preview-viewer");
  const viewerLoading = document.getElementById("model-preview-loading");
  const viewerError = document.getElementById("model-preview-error");
  if (!modelViewer || !viewerLoading) return;

  const viewer = window.PickAPrintViewer?.bind(modelViewer, viewerLoading, viewerError, {
    errorMessage: "Could not load the 3D preview. Try downloading the STL and re-uploading.",
  });

  window.customElements?.whenDefined("model-viewer").then(() => {
    if (modelViewer.loaded) viewer?.hideLoading();
  });
})();
