(function () {
  const STATUS_LABELS = {
    up_to_date: { text: "Up to date", className: "badge-dep-ok" },
    update_available: { text: "Update available", className: "badge-dep-warn" },
    floating: { text: "Floating tag", className: "badge-dep-info" },
    not_installed: { text: "Not in base image", className: "badge-dep-muted" },
    check_failed: { text: "Check failed", className: "badge-dep-muted" },
    checking: { text: "Checking…", className: "badge-dep-muted" },
  };

  const panel = document.getElementById("about-panel");
  if (!panel) return;

  const checksUrl = panel.dataset.checksUrl;
  const metaEl = document.getElementById("about-meta");
  const rebuildBadge = document.getElementById("about-rebuild-badge");
  const refreshBtn = document.getElementById("about-refresh-btn");
  const tabDot = document.querySelector('.tab[href*="tab=about"] .tab-dot');

  function statusBadge(status) {
    const info = STATUS_LABELS[status] || STATUS_LABELS.check_failed;
    return `<span class="badge badge-dep ${info.className}">${info.text}</span>`;
  }

  function renderDockerImages(images) {
    const tbody = document.getElementById("about-docker-body");
    if (!tbody) return;
    tbody.innerHTML = images
      .map(
        (img) => `
      <tr>
        <td>
          <strong>${img.service}</strong>
          <div class="dep-source">${img.source}</div>
        </td>
        <td><code>${img.image}</code></td>
        <td><code>${img.tag}</code></td>
        <td>${img.latest ? img.latest : '<span class="text-muted">—</span>'}</td>
        <td>${statusBadge(img.status)}</td>
      </tr>`
      )
      .join("");
  }

  function renderPipelineTools(tools) {
    const tbody = document.getElementById("about-tools-body");
    if (!tbody) return;
    tbody.innerHTML = tools
      .map(
        (tool) => `
      <tr>
        <td>
          <strong>${tool.name}</strong>
          <div class="dep-source">${tool.source}</div>
        </td>
        <td>${tool.installed ? tool.installed : '<span class="text-muted">—</span>'}</td>
        <td>${tool.latest ? tool.latest : '<span class="text-muted">—</span>'}</td>
        <td>${statusBadge(tool.status)}</td>
      </tr>`
      )
      .join("");
  }

  function setLoading(loading) {
    panel.classList.toggle("about-loading", loading);
    if (refreshBtn) {
      refreshBtn.disabled = loading;
      refreshBtn.textContent = loading ? "Checking…" : "Refresh checks";
    }
  }

  function applyData(data) {
    renderDockerImages(data.docker_images || []);
    renderPipelineTools(data.pipeline_tools || []);

    if (metaEl) {
      const cacheNote = data.from_cache ? "cached" : "live";
      metaEl.textContent = `Last checked ${data.checked_at} (${cacheNote}) · results cached for ${data.cache_ttl_minutes} min`;
    }

    if (rebuildBadge) {
      rebuildBadge.hidden = !data.updates_available;
    }

    if (tabDot) {
      tabDot.hidden = !data.updates_available;
    } else if (data.updates_available) {
      const aboutTab = document.querySelector('a.tab[href*="tab=about"]');
      if (aboutTab && !aboutTab.querySelector(".tab-dot")) {
        aboutTab.insertAdjacentHTML("beforeend", '<span class="tab-dot" title="Updates available"></span>');
      }
    }
  }

  async function loadChecks(refresh) {
    const isSkeleton = Boolean(panel.querySelector("#about-docker-body .badge-dep-muted"));
    setLoading(refresh || isSkeleton);
    try {
      const url = refresh ? `${checksUrl}?refresh=1` : checksUrl;
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      applyData(await res.json());
    } catch (err) {
      if (metaEl) metaEl.textContent = "Could not check for updates. Try Refresh checks.";
      console.error("about checks failed", err);
    } finally {
      setLoading(false);
    }
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", (e) => {
      e.preventDefault();
      loadChecks(true);
    });
  }

  loadChecks(false);
})();
