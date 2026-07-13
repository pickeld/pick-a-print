document.addEventListener("DOMContentLoaded", () => {
  const page = document.getElementById("model-parts-page");
  const grid = document.getElementById("model-parts-grid");
  const form = document.getElementById("parts-bulk-form");
  const editBtn = document.getElementById("parts-edit-btn");
  if (!page || !grid) return;

  const selectAll = document.getElementById("select-all-parts");
  const deleteBtn = document.getElementById("parts-delete-btn");
  const downloadBtn = document.getElementById("parts-download-btn");
  const countWrap = document.getElementById("parts-selection-count");
  const countNumber = document.getElementById("parts-selection-number");
  const pencilIcon = editBtn?.querySelector(".icon-pencil");
  const doneIcon = editBtn?.querySelector(".icon-done");

  const modal = document.getElementById("part-preview-modal");
  const modalViewer = document.getElementById("part-preview-modal-viewer");
  const modalLoading = document.getElementById("part-preview-modal-loading");
  const modalError = document.getElementById("part-preview-modal-error");
  const modalTitle = document.getElementById("part-preview-modal-title");
  const modalClose = document.getElementById("part-preview-modal-close");

  const checkboxes = () => Array.from(grid.querySelectorAll('input[name="file_ids"]'));

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

  const modalViewerUi =
    modalViewer && modalLoading
      ? window.PickAPrintViewer?.bind(modalViewer, modalLoading, modalError, {
          errorMessage: "Could not load the 3D preview.",
        })
      : null;

  function clearSelection() {
    checkboxes().forEach((box) => {
      box.checked = false;
    });
    if (selectAll) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    }
    updateSelection();
  }

  function setEditMode(enabled) {
    page.classList.toggle("is-editing", enabled);
    editBtn?.setAttribute("aria-pressed", enabled ? "true" : "false");
    editBtn?.setAttribute("aria-label", enabled ? "Done selecting" : "Select parts");
    editBtn?.setAttribute("title", enabled ? "Done" : "Select parts");
    editBtn?.classList.toggle("is-active", enabled);

    if (pencilIcon) pencilIcon.hidden = enabled;
    if (doneIcon) doneIcon.hidden = !enabled;

    if (!enabled) clearSelection();
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

  function openPreviewModal(previewUrl, fileName) {
    if (!modal || !modalViewer || !previewUrl) return;

    modalTitle.textContent = fileName || "3D preview";
    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    modalViewerUi?.showLoading();

    window.customElements.whenDefined("model-viewer").then(() => {
      modalViewer.setAttribute("src", previewUrl);
      if (typeof modalViewer.dismissPoster === "function") {
        modalViewer.dismissPoster();
      }
      modalViewer.cameraOrbit = "auto auto auto";
    });
  }

  function closePreviewModal() {
    if (!modal || !modalViewer) return;
    modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
    modalViewer.removeAttribute("src");
  }

  editBtn?.addEventListener("click", () => {
    setEditMode(!page.classList.contains("is-editing"));
  });

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
    const expandBtn = event.target.closest(".part-card-expand");
    if (expandBtn) {
      event.stopPropagation();
      openPreviewModal(expandBtn.dataset.previewUrl, expandBtn.dataset.fileName);
      return;
    }

    if (!page.classList.contains("is-editing")) return;

    if (event.target.closest(".part-card-download") || event.target.closest(".part-card-check")) return;

    const card = event.target.closest(".part-card--selectable");
    if (!card) return;

    const box = card.querySelector('input[name="file_ids"]');
    if (!box) return;

    event.preventDefault();
    box.checked = !box.checked;
    updateSelection();
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

  modalClose?.addEventListener("click", closePreviewModal);
  modal?.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closePreviewModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.classList.contains("hidden")) {
      closePreviewModal();
    }
  });

  setEditMode(false);
});
