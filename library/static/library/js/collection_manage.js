document.addEventListener("DOMContentLoaded", () => {
  initCollectionFormModal();
  document.querySelectorAll("[data-collection-manage]").forEach(initCollectionManage);
  document.querySelectorAll("[data-collection-edit-trigger]").forEach(initCollectionEditTrigger);
});

const DEFAULT_COLLECTION_ICON = "folder";
const MAX_VISIBLE_ICONS = 120;

let allMdiIcons = null;
let mdiIconsPromise = null;

function readSuggestedIcons() {
  const data = document.getElementById("collection-icons-data");
  if (!data) return [DEFAULT_COLLECTION_ICON];
  try {
    const icons = JSON.parse(data.textContent);
    return Array.isArray(icons) && icons.length ? icons : [DEFAULT_COLLECTION_ICON];
  } catch {
    return [DEFAULT_COLLECTION_ICON];
  }
}

function loadMdiIcons(modal) {
  if (allMdiIcons) return Promise.resolve(allMdiIcons);
  if (mdiIconsPromise) return mdiIconsPromise;

  const url = modal?.dataset.mdiIconsUrl;
  if (!url) {
    allMdiIcons = readSuggestedIcons();
    return Promise.resolve(allMdiIcons);
  }

  mdiIconsPromise = fetch(url)
    .then((response) => {
      if (!response.ok) throw new Error("Failed to load icons");
      return response.json();
    })
    .then((icons) => {
      allMdiIcons = Array.isArray(icons) && icons.length ? icons : readSuggestedIcons();
      return allMdiIcons;
    })
    .catch(() => {
      allMdiIcons = readSuggestedIcons();
      return allMdiIcons;
    });

  return mdiIconsPromise;
}

function iconLabel(iconName) {
  return iconName.replace(/-/g, " ");
}

function filterIcons(query, suggested, allIcons) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return suggested;
  return allIcons.filter((icon) => icon.includes(normalized)).slice(0, MAX_VISIBLE_ICONS);
}

function buildVisibleIcons(query, suggested, allIcons, selectedIcon) {
  const icons = filterIcons(query, suggested, allIcons);
  if (selectedIcon && !icons.includes(selectedIcon) && isValidIconName(selectedIcon)) {
    return [selectedIcon, ...icons];
  }
  return icons;
}

function isValidIconName(iconName) {
  return typeof iconName === "string" && /^[a-z0-9][a-z0-9-]*$/.test(iconName);
}

function renderIconButtons(picker, icons, selectedIcon) {
  if (!picker) return;

  if (!icons.length) {
    picker.innerHTML = `<p class="collection-icon-picker__empty">No icons match your search.</p>`;
    return;
  }

  picker.innerHTML = icons
    .map((icon) => {
      const selected = icon === selectedIcon;
      const label = iconLabel(icon);
      return `
        <button
          type="button"
          class="collection-icon-option${selected ? " is-selected" : ""}"
          data-collection-icon-option="${icon}"
          aria-label="${label}"
          aria-pressed="${selected ? "true" : "false"}"
          title="${label}"
        >
          <span class="mdi mdi-${icon}" aria-hidden="true"></span>
        </button>
      `;
    })
    .join("");
}

function updateIconHint(hint, query, visibleCount, totalMatches) {
  if (!hint) return;

  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    hint.textContent = "Popular icons — search for any Material Design icon";
    return;
  }

  if (visibleCount === 0) {
    hint.textContent = "No icons match your search";
    return;
  }

  if (totalMatches > MAX_VISIBLE_ICONS) {
    hint.textContent = `Showing ${visibleCount} of ${totalMatches} matches — refine your search`;
    return;
  }

  hint.textContent = `${visibleCount} icon${visibleCount === 1 ? "" : "s"} found`;
}

function collectionEditAction(id) {
  return `/collections/${id}/edit/`;
}

function readCollectionFromElement(element) {
  const id = Number.parseInt(element.dataset.collectionId || "", 10);
  if (!Number.isFinite(id)) return null;
  return {
    id,
    name: element.dataset.collectionName || "",
    icon: element.dataset.collectionIcon || DEFAULT_COLLECTION_ICON,
  };
}

function initCollectionFormModal() {
  const modal = document.querySelector("[data-collection-form-modal]");
  const form = modal?.querySelector("[data-collection-form]");
  if (!modal || !form) return;

  const title = modal.querySelector("[data-collection-modal-title]");
  const submitBtn = form.querySelector("[data-collection-submit-btn]");
  const nameInput = form.querySelector("[data-collection-name-input]");
  const iconInput = form.querySelector("[data-collection-icon-input]");
  const nextInput = form.querySelector("[data-collection-next-input]");
  const picker = form.querySelector("[data-collection-icon-picker]");
  const searchInput = form.querySelector("[data-collection-icon-search]");
  const hint = form.querySelector("[data-collection-icon-hint]");
  const suggestedIcons = readSuggestedIcons();
  const createAction = form.dataset.collectionCreateAction || form.getAttribute("action");

  let currentQuery = "";
  let selectedIcon = iconInput?.value || DEFAULT_COLLECTION_ICON;
  let modalMode = "create";

  const countMatches = (query, allIcons) => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return suggestedIcons.length;
    return allIcons.filter((icon) => icon.includes(normalized)).length;
  };

  const setIcon = (iconName, allIcons) => {
    const icon =
      allIcons?.includes(iconName) || suggestedIcons.includes(iconName)
        ? iconName
        : isValidIconName(iconName)
          ? iconName
          : DEFAULT_COLLECTION_ICON;
    selectedIcon = icon;
    if (iconInput) iconInput.value = icon;
    picker?.querySelectorAll("[data-collection-icon-option]").forEach((button) => {
      const isSelected = button.dataset.collectionIconOption === icon;
      button.classList.toggle("is-selected", isSelected);
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
  };

  const refreshPicker = async () => {
    const allIcons = await loadMdiIcons(modal);
    const totalMatches = countMatches(currentQuery, allIcons);
    const icons = buildVisibleIcons(currentQuery, suggestedIcons, allIcons, selectedIcon);
    renderIconButtons(picker, icons, selectedIcon);
    updateIconHint(hint, currentQuery, icons.length, totalMatches);
  };

  if (picker && !picker.dataset.ready) {
    picker.dataset.ready = "1";

    picker.addEventListener("click", (event) => {
      const button = event.target.closest("[data-collection-icon-option]");
      if (!button) return;
      setIcon(button.dataset.collectionIconOption, allMdiIcons);
    });

    searchInput?.addEventListener("input", () => {
      currentQuery = searchInput.value;
      refreshPicker();
    });
  }

  const configureModal = (mode, collection = null) => {
    modalMode = mode;

    if (mode === "edit" && collection) {
      if (title) title.textContent = "Edit collection";
      if (submitBtn) submitBtn.textContent = "Save";
      form.action = collectionEditAction(collection.id);
      if (nameInput) nameInput.value = collection.name;
      selectedIcon = collection.icon || DEFAULT_COLLECTION_ICON;
      if (iconInput) iconInput.value = selectedIcon;
    } else {
      if (title) title.textContent = "New collection";
      if (submitBtn) submitBtn.textContent = "Create";
      form.action = createAction;
      if (nameInput) nameInput.value = "";
      selectedIcon = DEFAULT_COLLECTION_ICON;
      if (iconInput) iconInput.value = selectedIcon;
    }

    if (searchInput) searchInput.value = "";
    currentQuery = "";
  };

  const openModal = (mode = "create", collection = null) => {
    modal.hidden = false;
    document.body.classList.add("collection-modal-open");
    if (nextInput) nextInput.value = window.location.pathname;
    configureModal(mode, collection);
    refreshPicker().then(() => {
      setIcon(selectedIcon, allMdiIcons);
      nameInput?.focus();
    });
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

  window.openCollectionCreateModal = () => openModal("create");
  window.openCollectionEditModal = (collection) => {
    if (!collection?.id) return;
    openModal("edit", collection);
  };
  window.closeCollectionFormModal = closeModal;

  if (modal.dataset.openOnLoad === "1") {
    const mode = modal.dataset.openMode === "edit" ? "edit" : "create";
    const collection =
      mode === "edit"
        ? {
            id: Number.parseInt(modal.dataset.openCollectionId || "", 10),
            name: nameInput?.value || "",
            icon: iconInput?.value || DEFAULT_COLLECTION_ICON,
          }
        : null;
    openModal(mode, collection);
  }
}

function initCollectionEditTrigger(button) {
  button.addEventListener("click", () => {
    const collection = readCollectionFromElement(button);
    if (!collection) return;
    window.openCollectionEditModal?.(collection);
  });
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

    const collection = readCollectionFromElement(item);
    if (!collection) return;

    event.preventDefault();
    window.openCollectionEditModal?.(collection);
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

// Backwards-compatible alias used by older inline scripts.
window.closeCollectionCreateModal = () => window.closeCollectionFormModal?.();
