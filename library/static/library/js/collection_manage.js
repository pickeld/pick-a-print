document.addEventListener("DOMContentLoaded", () => {
  initCollectionCreateModal();
  document.querySelectorAll("[data-collection-manage]").forEach(initCollectionManage);
});

const DEFAULT_COLLECTION_ICON = "folder";

function readCollectionIcons() {
  const data = document.getElementById("collection-icons-data");
  if (!data) return [DEFAULT_COLLECTION_ICON];
  try {
    const icons = JSON.parse(data.textContent);
    return Array.isArray(icons) && icons.length ? icons : [DEFAULT_COLLECTION_ICON];
  } catch {
    return [DEFAULT_COLLECTION_ICON];
  }
}

function initCollectionCreateModal() {
  const modal = document.querySelector("[data-collection-create-modal]");
  const form = modal?.querySelector("[data-collection-create-form]");
  if (!modal || !form) return;

  const nameInput = form.querySelector("[data-collection-name-input]");
  const iconInput = form.querySelector("[data-collection-icon-input]");
  const nextInput = form.querySelector("[data-collection-next-input]");
  const picker = form.querySelector("[data-collection-icon-picker]");
  const icons = readCollectionIcons();

  const setIcon = (iconName) => {
    const icon = icons.includes(iconName) ? iconName : DEFAULT_COLLECTION_ICON;
    if (iconInput) iconInput.value = icon;
    picker?.querySelectorAll("[data-collection-icon-option]").forEach((button) => {
      const selected = button.dataset.collectionIconOption === icon;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
  };

  if (picker && !picker.dataset.ready) {
    picker.dataset.ready = "1";
    picker.innerHTML = icons
      .map(
        (icon) => `
          <button
            type="button"
            class="collection-icon-option"
            data-collection-icon-option="${icon}"
            aria-label="${icon.replace(/-/g, " ")}"
            aria-pressed="false"
            title="${icon.replace(/-/g, " ")}"
          >
            <span class="mdi mdi-${icon}" aria-hidden="true"></span>
          </button>
        `
      )
      .join("");

    picker.addEventListener("click", (event) => {
      const button = event.target.closest("[data-collection-icon-option]");
      if (!button) return;
      setIcon(button.dataset.collectionIconOption);
    });
  }

  const openModal = () => {
    modal.hidden = false;
    document.body.classList.add("collection-modal-open");
    if (nextInput) nextInput.value = window.location.pathname;
    if (nameInput) {
      nameInput.value = "";
    }
    setIcon(iconInput?.value || DEFAULT_COLLECTION_ICON);
    nameInput?.focus();
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove("collection-modal-open");
    document.querySelectorAll("[data-collection-manage]").forEach((root) => {
      root.classList.remove("is-creating");
      const addBtn = root.querySelector("[data-collection-add]");
      addBtn?.classList.remove("is-active");
      addBtn?.setAttribute("aria-pressed", "false");
    });
  };

  modal.querySelectorAll("[data-collection-modal-close]").forEach((button) => {
    button.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });

  window.openCollectionCreateModal = openModal;
  window.closeCollectionCreateModal = closeModal;

  if (modal.dataset.openOnLoad === "1") {
    openModal();
  }
}

function initCollectionManage(root) {
  const addBtn = root.querySelector("[data-collection-add]");
  const editBtn = root.querySelector("[data-collection-edit]");
  const bulkForm = root.querySelector("[data-collection-bulk-form]");
  const deleteBtn = root.querySelector("[data-collection-delete-btn]");
  if (!addBtn && !editBtn) return;

  const addLabel = addBtn?.querySelector(".collection-manage-btn__label");
  const editLabel = editBtn?.querySelector(".edit-mode-toggle__label");
  const pencilIcon = editBtn?.querySelector(".icon-pencil");
  const doneIcon = editBtn?.querySelector(".icon-done");
  const checkboxes = () => Array.from(root.querySelectorAll('input[name="collection_ids"]'));

  const clearSelection = () => {
    checkboxes().forEach((box) => {
      box.checked = false;
    });
    updateSelection();
  };

  const openCreateModal = () => {
    setEditMode(false);
    window.openCollectionCreateModal?.();
    if (addBtn) {
      root.classList.add("is-creating");
      addBtn.classList.add("is-active");
      addBtn.setAttribute("aria-pressed", "true");
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

    if (!enabled) {
      clearSelection();
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

  addBtn?.addEventListener("click", () => {
    openCreateModal();
    if (addLabel) {
      addBtn.setAttribute("title", "New collection");
      addLabel.textContent = addBtn.dataset.labelOpen || "New";
    }
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
    if (event.target.closest(".collection-card-check")) return;

    const item = event.target.closest("[data-collection-item]");
    if (!item) return;

    const box = item.querySelector('input[name="collection_ids"]');
    if (!box) return;

    event.preventDefault();
    box.checked = !box.checked;
    updateSelection();
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
}
