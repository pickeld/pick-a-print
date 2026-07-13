document.addEventListener("DOMContentLoaded", () => {
  const page = document.getElementById("model-parts-page");
  const grid = document.getElementById("model-parts-grid");
  const form = document.getElementById("parts-bulk-form");
  if (!page || !grid) return;

  const selectAll = document.getElementById("select-all-parts");
  const deleteBtn = document.getElementById("parts-delete-btn");
  const downloadBtn = document.getElementById("parts-download-btn");
  const countWrap = document.getElementById("parts-selection-count");
  const countNumber = document.getElementById("parts-selection-number");

  const mainSection = document.getElementById("part-main-viewer");
  const mainViewer = document.getElementById("part-main-viewer-canvas");
  const mainLoading = document.getElementById("part-main-viewer-loading");
  const mainError = document.getElementById("part-main-viewer-error");
  const mainTitle = document.getElementById("part-main-viewer-title");

  const checkboxes = () => Array.from(grid.querySelectorAll('input[name="file_ids"]'));

  let activeFileId = mainSection?.dataset.activeFileId || null;

  const mainViewerUi =
    mainViewer && mainLoading
      ? window.PickAPrintViewer?.bind(mainViewer, mainLoading, mainError, {
          errorMessage: "Could not load the 3D preview.",
        })
      : null;

  function bindCardViewer(viewer) {
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
  }

  grid.querySelectorAll(".part-card-preview model-viewer").forEach(bindCardViewer);

  function setActivePartCard(fileId) {
    activeFileId = String(fileId);
    if (mainSection) mainSection.dataset.activeFileId = activeFileId;

    grid.querySelectorAll(".part-card--previewable").forEach((card) => {
      card.classList.toggle("part-card--active", card.dataset.fileId === activeFileId);
    });
  }

  function showInMainViewer(previewUrl, fileName, fileId) {
    if (!mainViewer || !previewUrl || String(fileId) === String(activeFileId)) return;

    setActivePartCard(fileId);
    if (mainTitle) mainTitle.textContent = fileName || "3D preview";
    mainViewerUi?.showLoading();

    window.customElements.whenDefined("model-viewer").then(() => {
      mainViewer.setAttribute("src", previewUrl);
      if (typeof mainViewer.dismissPoster === "function") {
        mainViewer.dismissPoster();
      }
      mainViewer.cameraOrbit = "auto auto auto";
    });

    mainSection?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function updateSelection() {
    const boxes = checkboxes();
    const selected = boxes.filter((box) => box.checked);
    const count = selected.length;

    if (countNumber) countNumber.textContent = String(count);
    if (countWrap) countWrap.hidden = count === 0;
    if (deleteBtn) deleteBtn.disabled = count === 0;
    if (downloadBtn) downloadBtn.disabled = count === 0;

    if (selectAll) {
      selectAll.indeterminate = count > 0 && count < boxes.length;
      selectAll.checked = boxes.length > 0 && count === boxes.length;
    }

    boxes.forEach((box) => {
      const card = box.closest(".part-card");
      if (card) card.classList.toggle("is-selected", box.checked);
    });
  }

  selectAll?.addEventListener("change", () => {
    const checked = selectAll.checked;
    checkboxes().forEach((box) => {
      box.checked = checked;
    });
    updateSelection();
  });

  grid.addEventListener("change", (event) => {
    if (event.target.matches('input[name="file_ids"]')) {
      updateSelection();
    }
  });

  grid.addEventListener("click", (event) => {
    if (event.target.closest(".part-card-download") || event.target.closest(".part-card-check")) return;

    const previewCard = event.target.closest(".part-card--previewable");
    if (previewCard) {
      showInMainViewer(
        previewCard.dataset.previewUrl,
        previewCard.dataset.fileName,
        previewCard.dataset.fileId,
      );
    }
  });

  form?.addEventListener("submit", (event) => {
    const submitter = event.submitter;
    const selectedCount = checkboxes().filter((box) => box.checked).length;
    if (selectedCount === 0) {
      event.preventDefault();
      return;
    }

    if (submitter === deleteBtn) {
      const message = deleteBtn.dataset.confirm || "Delete selected parts?";
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    }
  });

  window.customElements?.whenDefined("model-viewer").then(() => {
    if (mainViewer?.loaded) mainViewerUi?.hideLoading();
  });

  updateSelection();
});
