document.addEventListener("DOMContentLoaded", () => {
  initCollectionDrop();
});

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta?.content) return meta.content;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function showCollectionDropToast(message, type = "success") {
  let toast = document.getElementById("collection-drop-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "collection-drop-toast";
    toast.className = "collection-drop-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.className = `collection-drop-toast collection-drop-toast--${type} is-visible`;
  window.clearTimeout(toast._hideTimer);
  toast._hideTimer = window.setTimeout(() => {
    toast.classList.remove("is-visible");
  }, 2800);
}

function isBulkEditActive() {
  return Boolean(document.querySelector(".model-bulk-page.is-editing"));
}

function readDraggedModel(source) {
  const id = Number.parseInt(source.dataset.modelId || "", 10);
  if (!Number.isFinite(id)) return null;
  return {
    id,
    title: source.dataset.modelTitle || "Model",
  };
}

function updateCollectionCount(collectionId, count) {
  document.querySelectorAll(`[data-collection-count="${collectionId}"]`).forEach((element) => {
    element.textContent = String(count);
  });
}

async function addModelToCollection(modelId, collectionId) {
  const response = await fetch(`/collections/${collectionId}/add-model/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify({ model_id: modelId }),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Could not add model to collection.");
  }
  return data;
}

function initCollectionDrop() {
  const dropTargets = Array.from(document.querySelectorAll("[data-collection-drop-target]"));
  if (!dropTargets.length) return;

  let activeDrag = null;

  const clearDropTargetState = () => {
    dropTargets.forEach((target) => target.classList.remove("is-drop-target"));
    document.body.classList.remove("is-model-dragging");
    activeDrag = null;
  };

  document.querySelectorAll("[data-model-card][draggable='true']").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      if (isBulkEditActive()) {
        event.preventDefault();
        return;
      }

      const model = readDraggedModel(card);
      if (!model) {
        event.preventDefault();
        return;
      }

      activeDrag = model;
      event.dataTransfer.effectAllowed = "copy";
      event.dataTransfer.setData("text/plain", String(model.id));
      card.classList.add("is-dragging");
      document.body.classList.add("is-model-dragging");
    });

    card.addEventListener("dragend", () => {
      card.classList.remove("is-dragging");
      clearDropTargetState();
    });
  });

  dropTargets.forEach((target) => {
    target.addEventListener("dragenter", (event) => {
      if (!activeDrag) return;
      event.preventDefault();
      target.classList.add("is-drop-target");
    });

    target.addEventListener("dragover", (event) => {
      if (!activeDrag) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      target.classList.add("is-drop-target");
    });

    target.addEventListener("dragleave", (event) => {
      const rect = target.getBoundingClientRect();
      const { clientX, clientY } = event;
      const inside =
        clientX >= rect.left &&
        clientX <= rect.right &&
        clientY >= rect.top &&
        clientY <= rect.bottom;
      if (!inside) {
        target.classList.remove("is-drop-target");
      }
    });

    target.addEventListener("drop", async (event) => {
      event.preventDefault();
      target.classList.remove("is-drop-target");

      const model = activeDrag;
      const collectionId = Number.parseInt(target.dataset.collectionId || "", 10);
      const collectionName = target.dataset.collectionName || "collection";
      clearDropTargetState();

      if (!model || !Number.isFinite(collectionId)) return;

      target.classList.add("is-drop-loading");
      try {
        const result = await addModelToCollection(model.id, collectionId);
        updateCollectionCount(collectionId, result.model_count);
        showCollectionDropToast(
          result.message || `Added "${model.title}" to "${collectionName}".`,
          result.already_member ? "info" : "success"
        );
      } catch (error) {
        showCollectionDropToast(error.message || "Could not add model to collection.", "error");
      } finally {
        target.classList.remove("is-drop-loading");
      }
    });
  });
}
