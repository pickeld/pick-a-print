(() => {
  const SCAN_EXTENSIONS = new Set([
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v",
    ".zip",
  ]);
  const MODEL_EXTENSIONS = new Set([".stl", ".3mf"]);

  const body = document.body;
  const overlay = document.getElementById("file-drop-overlay");
  if (!overlay || !body.dataset.scanUploadUrl || !body.dataset.modelUploadUrl) return;

  const scanUrl = body.dataset.scanUploadUrl;
  const modelUrl = body.dataset.modelUploadUrl;
  const statusEl = overlay.querySelector(".file-drop-status");
  const hintEl = overlay.querySelector(".file-drop-hint");

  let dragDepth = 0;
  let uploading = false;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta?.content) return meta.content;
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function fileExtension(name) {
    const dot = name.lastIndexOf(".");
    return dot >= 0 ? name.slice(dot).toLowerCase() : "";
  }

  function classifyFile(file) {
    const ext = fileExtension(file.name);
    if (MODEL_EXTENSIONS.has(ext)) return "model";
    if (SCAN_EXTENSIONS.has(ext)) return "scan";
    if (file.type.startsWith("image/") || file.type.startsWith("video/")) return "scan";
    if (file.type === "application/zip") return "scan";
    return null;
  }

  function isFileDrag(event) {
    return [...(event.dataTransfer?.types || [])].includes("Files");
  }

  function setStatus(message) {
    if (statusEl) statusEl.textContent = message;
  }

  function showOverlay(kind) {
    overlay.hidden = false;
    overlay.classList.add("file-drop-overlay--active");
    if (kind === "model") {
      setStatus("Drop to save model");
      if (hintEl) hintEl.textContent = ".stl · .3mf";
    } else if (kind === "scan") {
      setStatus("Drop to start scan");
      if (hintEl) hintEl.textContent = "photos · video · .zip";
    } else if (kind === "mixed") {
      setStatus("Drop files to upload");
      if (hintEl) hintEl.textContent = "scan media and model files will be routed automatically";
    } else {
      setStatus("Drop files to upload");
      if (hintEl) hintEl.textContent = "photos, video, zip → scan · stl, 3mf → library";
    }
  }

  function hideOverlay() {
    if (uploading) return;
    overlay.classList.remove("file-drop-overlay--active");
    overlay.hidden = true;
    dragDepth = 0;
  }

  function classifyFiles(files) {
    const scan = [];
    const model = [];
    const unsupported = [];

    for (const file of files) {
      const kind = classifyFile(file);
      if (kind === "scan") scan.push(file);
      else if (kind === "model") model.push(file);
      else unsupported.push(file);
    }

    return { scan, model, unsupported };
  }

  function previewKind(files) {
    const { scan, model } = classifyFiles(files);
    if (scan.length && model.length) return "mixed";
    if (model.length) return "model";
    if (scan.length) return "scan";
    return null;
  }

  async function postForm(url, fields) {
    const formData = new FormData();
    formData.append("csrfmiddlewaretoken", getCsrfToken());
    for (const [key, value] of Object.entries(fields)) {
      if (Array.isArray(value)) {
        value.forEach((item) => formData.append(key, item));
      } else {
        formData.append(key, value);
      }
    }

    return fetch(url, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      redirect: "follow",
    });
  }

  async function uploadModels(files) {
    let lastUrl = modelUrl;
    for (let i = 0; i < files.length; i += 1) {
      setStatus(`Uploading model ${i + 1} of ${files.length}…`);
      const response = await postForm(modelUrl, {
        save_upload: "1",
        "upload-file": files[i],
      });
      lastUrl = response.url;
      if (!response.ok && !response.redirected) {
        throw new Error(`Model upload failed (${response.status})`);
      }
    }
    return lastUrl;
  }

  async function uploadScan(files) {
    setStatus(`Starting scan with ${files.length} file${files.length === 1 ? "" : "s"}…`);
    const response = await postForm(scanUrl, { files });
    if (!response.ok && !response.redirected) {
      throw new Error(`Scan upload failed (${response.status})`);
    }
    return response.url;
  }

  async function handleFiles(fileList) {
    const files = [...fileList];
    if (!files.length || uploading) return;

    const { scan, model, unsupported } = classifyFiles(files);
    if (!scan.length && !model.length) {
      setStatus(
        unsupported.length === 1
          ? `Unsupported file: ${unsupported[0].name}`
          : `${unsupported.length} unsupported files`,
      );
      overlay.classList.add("file-drop-overlay--error");
      window.setTimeout(() => {
        overlay.classList.remove("file-drop-overlay--error");
        hideOverlay();
      }, 2400);
      return;
    }

    uploading = true;
    overlay.classList.add("file-drop-overlay--uploading");

    try {
      let redirectUrl = null;

      if (model.length) {
        redirectUrl = await uploadModels(model);
      }
      if (scan.length) {
        redirectUrl = await uploadScan(scan);
      }

      window.location.href = redirectUrl || (scan.length ? scanUrl : modelUrl);
    } catch (error) {
      uploading = false;
      overlay.classList.remove("file-drop-overlay--uploading");
      setStatus(error.message || "Upload failed");
      overlay.classList.add("file-drop-overlay--error");
      window.setTimeout(() => {
        overlay.classList.remove("file-drop-overlay--error");
        hideOverlay();
      }, 2800);
    }
  }

  window.addEventListener("dragenter", (event) => {
    if (!isFileDrag(event) || uploading) return;
    event.preventDefault();
    dragDepth += 1;
    const kind = previewKind(event.dataTransfer.files);
    showOverlay(kind);
  });

  window.addEventListener("dragover", (event) => {
    if (!isFileDrag(event) || uploading) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  });

  window.addEventListener("dragleave", (event) => {
    if (!isFileDrag(event) || uploading) return;
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) hideOverlay();
  });

  window.addEventListener("drop", (event) => {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    dragDepth = 0;
    const files = event.dataTransfer?.files;
    if (files?.length) handleFiles(files);
    else hideOverlay();
  });

  window.addEventListener("dragend", () => {
    if (!uploading) hideOverlay();
  });
})();
