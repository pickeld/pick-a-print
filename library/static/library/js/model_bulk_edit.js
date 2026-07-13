document.addEventListener("DOMContentLoaded", () => {
  const page = document.querySelector(".model-bulk-page");
  const form = document.getElementById("model-bulk-form");
  const grid = document.getElementById("model-bulk-grid");
  const editBtn = document.getElementById("model-bulk-edit-btn");
  if (!page || !form || !grid || !editBtn) return;

  const selectAll = document.getElementById("select-all-models");
  const deleteBtn = document.getElementById("bulk-delete-btn");
  const countWrap = document.getElementById("bulk-selection-count");
  const countNumber = document.getElementById("bulk-selection-number");
  const editLabel = editBtn.querySelector(".edit-mode-toggle__label");
  const checkboxes = () => Array.from(grid.querySelectorAll('input[name="model_ids"]'));

  const clearSelection = () => {
    checkboxes().forEach((box) => {
      box.checked = false;
    });
    if (selectAll) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    }
    updateSelection();
  };

  const setEditMode = (enabled) => {
    page.classList.toggle("is-editing", enabled);
    editBtn.setAttribute("aria-pressed", enabled ? "true" : "false");
    const editText = editBtn.dataset.labelEdit || "Edit";
    const doneText = editBtn.dataset.labelDone || "Done";
    editBtn.setAttribute("aria-label", enabled ? "Done editing" : "Edit models");
    editBtn.setAttribute("title", enabled ? doneText : "Edit models");
    editBtn.classList.toggle("is-active", enabled);
    if (editLabel) editLabel.textContent = enabled ? doneText : editText;

    if (!enabled) {
      clearSelection();
    }
  };

  const updateSelection = () => {
    const boxes = checkboxes();
    const selected = boxes.filter((box) => box.checked);
    const count = selected.length;

    if (countNumber) countNumber.textContent = String(count);
    if (countWrap) countWrap.hidden = count === 0;
    if (deleteBtn) deleteBtn.disabled = count === 0;

    if (selectAll) {
      selectAll.indeterminate = count > 0 && count < boxes.length;
      selectAll.checked = boxes.length > 0 && count === boxes.length;
    }

    boxes.forEach((box) => {
      const wrap = box.closest(".model-card-wrap");
      if (wrap) wrap.classList.toggle("is-selected", box.checked);
    });
  };

  editBtn.addEventListener("click", () => {
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
    if (event.target.matches('input[name="model_ids"]')) {
      updateSelection();
    }
  });

  grid.addEventListener("click", (event) => {
    if (!page.classList.contains("is-editing")) return;
    const link = event.target.closest(".model-card");
    if (link) {
      event.preventDefault();
    }
  });

  form.addEventListener("submit", (event) => {
    const count = checkboxes().filter((box) => box.checked).length;
    if (count === 0) {
      event.preventDefault();
      return;
    }

    const message = deleteBtn?.dataset.confirm || "Delete selected models?";
    if (!window.confirm(message)) {
      event.preventDefault();
    }
  });

  setEditMode(false);
});
