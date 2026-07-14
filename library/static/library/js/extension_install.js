(function () {
  const downloadBtn = document.getElementById("extension-download-btn");
  if (!downloadBtn) return;

  downloadBtn.addEventListener("click", () => {
    downloadBtn.textContent = "Downloading…";
    window.setTimeout(() => {
      const version = downloadBtn.textContent.match(/v[\d.]+/)?.[0] || "";
      downloadBtn.textContent = version ? `Download extension (${version})` : "Download extension";
    }, 2500);
  });
})();
