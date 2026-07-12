document.addEventListener("DOMContentLoaded", () => {
  const uploadForm = document.getElementById("upload-stl-form");
  const uploadBtn = document.getElementById("upload-stl-btn");

  if (uploadForm && uploadBtn) {
    uploadForm.addEventListener("submit", () => {
      const fileInput = uploadForm.querySelector('input[type="file"]');
      if (!fileInput?.files?.length) return;

      uploadBtn.disabled = true;
      uploadBtn.textContent = "Uploading…";
    });
  }

  const urlForm = document.getElementById("save-url-form");
  const urlBtn = document.getElementById("save-url-btn");

  if (urlForm && urlBtn) {
    urlForm.addEventListener("submit", () => {
      urlBtn.disabled = true;
      urlBtn.textContent = "Saving…";
    });
  }
});
