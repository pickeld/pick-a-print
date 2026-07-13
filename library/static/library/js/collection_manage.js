document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-collection-manage]").forEach(initCollectionManage);
});

function initCollectionManage(root) {
  const addBtn = root.querySelector("[data-collection-add]");
  const editBtn = root.querySelector("[data-collection-edit]");
  const createForm = root.querySelector("[data-collection-create-form]");
  const bulkForm = root.querySelector("[data-collection-bulk-form]");
  const deleteBtn = root.querySelector("[data-collection-delete-btn]");
  const createPanel = root.querySelector("[data-collection-create-panel]");
  if (!addBtn) return;

  const addLabel = addBtn.querySelector(".collection-manage-btn__label");
  const editLabel = editBtn?.querySelector(".edit-mode-toggle__label");
  const pencilIcon = editBtn?.querySelector(".icon-pencil");
  const doneIcon = editBtn?.querySelector(".icon-done");
  const checkboxes = () => Array.from(root.querySelectorAll('input[name="collection_ids"]'));
  const checkLabels = () => Array.from(root.querySelectorAll(".collection-card-check"));

  const clearSelection = () => {
    checkboxes().forEach((box) => {
      box.checked = false;
    });
    updateSelection();
  };

  const setCreateOpen = (open) => {
    root.classList.toggle("is-creating", open);
    if (createPanel) {
      createPanel.hidden = !open;
    } else if (createForm) {
      createForm.hidden = !open;
    }
    addBtn.classList.toggle("is-active", open);
    addBtn.setAttribute("aria-pressed", open ? "true" : "false");
    if (addLabel) {
      addBtn.setAttribute("title", open ? (addBtn.dataset.labelClose || "Cancel") : "New collection");
      addLabel.textContent = open
        ? (addBtn.dataset.labelClose || "Cancel")
        : (addBtn.dataset.labelOpen || "New");
    } else {
      addBtn.setAttribute("title", open ? "Cancel" : "New collection");
    }
    if (open) {
      const nameInput =
        createPanel?.querySelector('input[name="name"]') ||
        createForm?.querySelector('input[name="name"]');
      nameInput?.focus();
    }
  };

  const setEditMode = (enabled) => {
    if (!editBtn) return;

    root.classList.toggle("is-editing", enabled);
    editBtn.setAttribute("aria-pressed", enabled ? "true" : "false");
    const editText = editBtn.dataset.labelEdit || "Edit";
    const doneText = editBtn.dataset.labelDone || "Done";
    editBtn.setAttribute("aria-label", enabled ? "Done editing" : "Edit collections");
    editBtn.setAttribute("title", enabled ? doneText : "Edit collections");
    editBtn.classList.toggle("is-active", enabled);
    if (editLabel) editLabel.textContent = enabled ? doneText : editText;
    if (pencilIcon) pencilIcon.hidden = enabled;
    if (doneIcon) doneIcon.hidden = !enabled;

    checkLabels().forEach((label) => {
      label.hidden = !enabled;
    });

    if (!enabled) {
      clearSelection();
    } else {
      setCreateOpen(false);
    }
  };

  const updateSelection = () => {
    const selected = checkboxes().filter((box) => box.checked);
    const count = selected.length;

    const countWrap = root.querySelector("[data-collection-selection-count]");
    const countNumber = root.querySelector("[data-collection-selection-number]");
    if (countNumber) countNumber.textContent = String(count);
    if (countWrap) countWrap.hidden = count === 0;
    if (deleteBtn) deleteBtn.disabled = count === 0;

    checkboxes().forEach((box) => {
      const item = box.closest("[data-collection-item]");
      if (item) item.classList.toggle("is-selected", box.checked);
    });
  };

  addBtn.addEventListener("click", () => {
    const open = !root.classList.contains("is-creating");
    if (open) setEditMode(false);
    setCreateOpen(open);
  });

  editBtn?.addEventListener("click", () => {
    setEditMode(!root.classList.contains("is-editing"));
  });

  root.addEventListener("change", (event) => {
    if (event.target.matches('input[name="collection_ids"]')) {
      updateSelection();
    }
  });

  root.addEventListener("click", (event) => {
    if (!root.classList.contains("is-editing")) return;

    const link = event.target.closest("[data-collection-link]");
    if (link) {
      event.preventDefault();
      const item = link.closest("[data-collection-item]");
      const box = item?.querySelector('input[name="collection_ids"]');
      if (box) {
        box.checked = !box.checked;
        updateSelection();
      }
    }
  });

  deleteBtn?.addEventListener("click", (event) => {
    if (!root.classList.contains("is-editing")) {
      event.preventDefault();
      return;
    }

    const count = checkboxes().filter((box) => box.checked).length;
    if (count === 0) {
      event.preventDefault();
      return;
    }

    const label = count === 1 ? "collection" : "collections";
    const message =
      deleteBtn.dataset.confirm ||
      `Delete ${count} selected ${label}? Models will be kept in your library.`;
    if (!window.confirm(message)) {
      event.preventDefault();
    }
  });

  bulkForm?.addEventListener("submit", (event) => {
    const count = checkboxes().filter((box) => box.checked).length;
    if (count === 0) {
      event.preventDefault();
    }
  });

  setEditMode(false);
  setCreateOpen(false);
}
