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
    if (event.target.closest(".part-card-download") || event.target.closest(".part-card-check")) return;

    const previewCard = event.target.closest(".part-card--previewable");
    if (previewCard && !page.classList.contains("is-editing")) {
      showInMainViewer(
        previewCard.dataset.previewUrl,
        previewCard.dataset.fileName,
        previewCard.dataset.fileId,
      );
      return;
    }

    if (!page.classList.contains("is-editing")) return;

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

  window.customElements?.whenDefined("model-viewer").then(() => {
    if (mainViewer?.loaded) mainViewerUi?.hideLoading();
  });

  setEditMode(false);
});
