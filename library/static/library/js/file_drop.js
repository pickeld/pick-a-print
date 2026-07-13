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
  const maxScanBytes = (parseInt(body.dataset.scanMaxUploadMb, 10) || 95) * 1024 * 1024;
  const cloudflareProxy = body.dataset.cloudflareProxy === "1";
  const statusEl = overlay.querySelector(".file-drop-status");
  const hintEl = overlay.querySelector(".file-drop-hint");
  const dropProgressWrap = document.getElementById("file-drop-progress");
  const dropProgressBar = document.getElementById("file-drop-progress-bar");
  const dropProgressLabel = document.getElementById("file-drop-progress-label");
  const dropProgressTrack = dropProgressWrap?.querySelector(".progress-track");

  const scanForm = document.getElementById("scan-upload-form");
  const scanSubmitBtn = document.getElementById("scan-submit-btn");
  const scanProgressWrap = document.getElementById("scan-upload-progress");
  const scanProgressBar = document.getElementById("scan-upload-progress-bar");
  const scanProgressLabel = document.getElementById("scan-upload-progress-label");
  const scanProgressTrack = scanProgressWrap?.querySelector(".progress-track");

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

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes < 1) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
  }

  function scanSizeError(files) {
    const total = files.reduce((sum, file) => sum + (file.size || 0), 0);
    if (total <= maxScanBytes) return null;
    const maxMb = Math.round(maxScanBytes / (1024 * 1024));
    if (cloudflareProxy) {
      return `Total ${formatBytes(total)} exceeds ${maxMb} MB. Cloudflare blocks proxied uploads over ~100 MB — use a smaller video, a .zip of photos, or upload on your home network.`;
    }
    return `Total ${formatBytes(total)} exceeds the ${maxMb} MB upload limit.`;
  }

  function payloadTooLargeMessage() {
    if (cloudflareProxy) {
      return "Upload blocked by Cloudflare (max ~100 MB). Use a smaller file or upload on your home network.";
    }
    return "Upload too large for the server.";
  }

  function setStatus(message) {
    if (statusEl) statusEl.textContent = message;
  }

  function updateProgressUI({ wrap, bar, label, track }, loaded, total, statusText) {
    if (!wrap || !bar || !label) return;
    wrap.hidden = false;

    if (loaded == null || total == null || total <= 0) {
      track?.classList.add("progress-track--indeterminate");
      bar.style.width = "35%";
      label.textContent = statusText || "Uploading…";
      return;
    }

    track?.classList.remove("progress-track--indeterminate");
    const percent = Math.min(100, Math.round((loaded / total) * 100));
    bar.style.width = `${percent}%`;
    label.textContent = statusText || `${percent}% · ${formatBytes(loaded)} / ${formatBytes(total)}`;
  }

  function resetProgressUI({ wrap, bar, label, track }) {
    if (!wrap || !bar || !label) return;
    wrap.hidden = true;
    bar.style.width = "0%";
    label.textContent = "Uploading…";
    track?.classList.remove("progress-track--indeterminate");
  }

  function showOverlay(kind) {
    overlay.hidden = false;
    overlay.classList.add("file-drop-overlay--active");
    resetProgressUI({
      wrap: dropProgressWrap,
      bar: dropProgressBar,
      label: dropProgressLabel,
      track: dropProgressTrack,
    });
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
    resetProgressUI({
      wrap: dropProgressWrap,
      bar: dropProgressBar,
      label: dropProgressLabel,
      track: dropProgressTrack,
    });
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

  function postFormXhr(url, fields, { onProgress } = {}) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append("csrfmiddlewaretoken", getCsrfToken());
      for (const [key, value] of Object.entries(fields)) {
        if (Array.isArray(value)) {
          value.forEach((item) => formData.append(key, item));
        } else if (value !== undefined && value !== null) {
          formData.append(key, value);
        }
      }

      xhr.open("POST", url);
      xhr.withCredentials = true;
      xhr.setRequestHeader("Accept", "application/json, text/html;q=0.9, */*;q=0.8");

      xhr.upload.addEventListener("progress", (event) => {
        if (!onProgress) return;
        if (event.lengthComputable) {
          onProgress(event.loaded, event.total);
        } else {
          onProgress(null, null);
        }
      });

      xhr.addEventListener("load", () => {
        resolve({
          status: xhr.status,
          responseURL: xhr.responseURL,
          responseText: xhr.responseText,
          getHeader: (name) => xhr.getResponseHeader(name),
        });
      });

      xhr.addEventListener("error", () => reject(new Error("Network error during upload")));
      xhr.addEventListener("abort", () => reject(new Error("Upload cancelled")));

      xhr.send(formData);
    });
  }

  function readUploadResponse(result, requestUrl, fallbackLabel) {
    const contentType = result.getHeader("content-type") || "";
    if (contentType.includes("application/json")) {
      let data;
      try {
        data = JSON.parse(result.responseText);
      } catch (_error) {
        throw new Error(`${fallbackLabel} failed`);
      }
      if (result.status >= 400) {
        throw new Error(data.error || `${fallbackLabel} failed`);
      }
      if (data.redirect) return data.redirect;
      throw new Error(data.error || `${fallbackLabel} failed`);
    }
    if (result.status === 413) {
      throw new Error(payloadTooLargeMessage());
    }
    if (result.status >= 400) {
      throw new Error(`${fallbackLabel} failed (${result.status})`);
    }
    if (result.responseURL && result.responseURL !== requestUrl) {
      return result.responseURL;
    }
    throw new Error(`${fallbackLabel} failed`);
  }

  async function uploadModels(files, progressUi) {
    let lastUrl = modelUrl;
    for (let i = 0; i < files.length; i += 1) {
      const file = files[i];
      setStatus(`Uploading model ${i + 1} of ${files.length}…`);
      if (hintEl) hintEl.textContent = file.name;
      const result = await postFormXhr(
        modelUrl,
        {
          save_upload: "1",
          "upload-file": file,
        },
        {
          onProgress: (loaded, total) => {
            updateProgressUI(
              progressUi,
              loaded,
              total,
              total
                ? `Model ${i + 1}/${files.length} · ${Math.round((loaded / total) * 100)}%`
                : `Model ${i + 1}/${files.length} · uploading…`,
            );
          },
        },
      );
      lastUrl = readUploadResponse(result, modelUrl, "Model upload");
    }
    return lastUrl;
  }

  async function uploadScan(files, progressUi) {
    const totalBytes = files.reduce((sum, file) => sum + (file.size || 0), 0);
    setStatus(`Starting scan with ${files.length} file${files.length === 1 ? "" : "s"}…`);
    if (hintEl) {
      hintEl.textContent = files.length === 1 ? files[0].name : `${files.length} files · ${formatBytes(totalBytes)}`;
    }
    const result = await postFormXhr(
      scanUrl,
      { files, file_drop: "1" },
      {
        onProgress: (loaded, total) => {
          updateProgressUI(
            progressUi,
            loaded,
            total,
            total
              ? `Uploading scan · ${Math.round((loaded / total) * 100)}% · ${formatBytes(loaded)} / ${formatBytes(total)}`
              : "Uploading scan…",
          );
        },
      },
    );
    return readUploadResponse(result, scanUrl, "Scan upload");
  }

  async function handleFiles(fileList) {
    const files = [...fileList];
    if (!files.length || uploading) return;

    const { scan, model, unsupported } = classifyFiles(files);
    const scanSizeLimitError = scan.length ? scanSizeError(scan) : null;
    if (scanSizeLimitError) {
      setStatus(scanSizeLimitError);
      overlay.classList.add("file-drop-overlay--error");
      window.setTimeout(() => {
        overlay.classList.remove("file-drop-overlay--error");
        hideOverlay();
      }, 4200);
      return;
    }
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
    const progressUi = {
      wrap: dropProgressWrap,
      bar: dropProgressBar,
      label: dropProgressLabel,
      track: dropProgressTrack,
    };

    try {
      let redirectUrl = null;

      if (model.length) {
        redirectUrl = await uploadModels(model, progressUi);
      }
      if (scan.length) {
        redirectUrl = await uploadScan(scan, progressUi);
      }

      updateProgressUI(progressUi, 1, 1, "Finishing…");
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

  if (scanForm && scanSubmitBtn) {
    scanForm.addEventListener("submit", async (event) => {
      if (scanSubmitBtn.disabled) return;
      event.preventDefault();

      const fileInput = scanForm.querySelector('input[name="files"]');
      const files = fileInput?.files ? [...fileInput.files] : [];
      if (!files.length) return;

      const scanSizeLimitError = scanSizeError(files);
      if (scanSizeLimitError) {
        resetProgressUI({
          wrap: scanProgressWrap,
          bar: scanProgressBar,
          label: scanProgressLabel,
          track: scanProgressTrack,
        });
        if (scanProgressWrap) scanProgressWrap.hidden = false;
        if (scanProgressLabel) {
          scanProgressLabel.textContent = scanSizeLimitError;
          scanProgressLabel.style.color = "var(--danger, #ef4444)";
        }
        return;
      }

      scanSubmitBtn.disabled = true;
      const progressUi = {
        wrap: scanProgressWrap,
        bar: scanProgressBar,
        label: scanProgressLabel,
        track: scanProgressTrack,
      };
      resetProgressUI(progressUi);
      if (scanProgressLabel) scanProgressLabel.style.color = "";
      updateProgressUI(progressUi, null, null, "Preparing upload…");

      const fields = { files, file_drop: "1" };
      for (const element of scanForm.elements) {
        if (!element.name || element === fileInput) continue;
        if (element.name === "csrfmiddlewaretoken") continue;
        if (element.type === "file" || element.type === "submit") continue;
        if ((element.type === "checkbox" || element.type === "radio") && !element.checked) continue;
        if (element.type === "select-multiple") {
          [...element.selectedOptions].forEach((option) => {
            fields[element.name] = fields[element.name] || [];
            fields[element.name].push(option.value);
          });
          continue;
        }
        fields[element.name] = element.value;
      }

      try {
        const result = await postFormXhr(scanUrl, fields, {
          onProgress: (loaded, total) => {
            updateProgressUI(
              progressUi,
              loaded,
              total,
              total
                ? `Uploading · ${Math.round((loaded / total) * 100)}% · ${formatBytes(loaded)} / ${formatBytes(total)}`
                : "Uploading…",
            );
          },
        });
        const redirectUrl = readUploadResponse(result, scanUrl, "Scan upload");
        updateProgressUI(progressUi, 1, 1, "Starting scan…");
        window.location.href = redirectUrl;
      } catch (error) {
        scanSubmitBtn.disabled = false;
        resetProgressUI(progressUi);
        if (scanProgressWrap) {
          scanProgressWrap.hidden = false;
          if (scanProgressLabel) {
            scanProgressLabel.textContent = error.message || "Upload failed";
            scanProgressLabel.style.color = "var(--danger, #ef4444)";
          }
        }
      }
    });
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
