(() => {
  const installBtns = document.querySelectorAll(".pwa-install-btn");
  const installedBadge = document.getElementById("pwa-installed-badge");
  const statusEl = document.getElementById("pwa-status");
  const shareUrl = document.body.dataset.shareUrl || "/share/";
  let deferredPrompt = null;

  const hideInstall = () => installBtns.forEach((btn) => btn.setAttribute("hidden", ""));

  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.matchMedia("(display-mode: window-controls-overlay)").matches ||
    window.navigator.standalone === true;

  const ua = navigator.userAgent || "";
  const isVivaldi = /Vivaldi/i.test(ua);
  const isChrome = /Chrome/i.test(ua) && !/EdgA|OPR|SamsungBrowser|Vivaldi/i.test(ua);
  const isSamsung = /SamsungBrowser/i.test(ua);

  function setStatus(message, kind = "info") {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.dataset.kind = kind;
    statusEl.hidden = false;
  }

  if (isStandalone) {
    hideInstall();
    installedBadge?.removeAttribute("hidden");
    if (isVivaldi) {
      setStatus(
        "Installed via Vivaldi. Android Share will NOT work — Vivaldi cannot register share targets. Reinstall with Chrome.",
        "error",
      );
    } else if (isChrome || isSamsung) {
      setStatus(
        "Installed app detected. Pick-a-Print should appear in Android Share after a Chrome/Samsung WebAPK install.",
        "ok",
      );
    } else {
      setStatus(
        "Installed app detected. If Share does not list Pick-a-Print, reinstall using Chrome on Android.",
        "warn",
      );
    }
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    if (!isStandalone) installBtns.forEach((btn) => btn.removeAttribute("hidden"));
    if (isVivaldi) {
      setStatus(
        "Install prompt available, but Vivaldi cannot add Pick-a-Print to Android Share. Use Chrome to install.",
        "warn",
      );
    } else {
      setStatus("Install is available. After installing via Chrome, Share → Pick-a-Print should appear.", "ok");
    }
  });

  installBtns.forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (isVivaldi) {
        setStatus("Open https://print.pickel.me in Chrome and install from there for Share support.", "warn");
        return;
      }
      if (!deferredPrompt) {
        setStatus("No install prompt yet. Use Chrome → menu → Install app.", "warn");
        return;
      }
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      hideInstall();
    });
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    hideInstall();
    installedBadge?.removeAttribute("hidden");
    if (!isVivaldi) {
      setStatus("Installed. Remove any Vivaldi copy, then test Share → Pick-a-Print.", "ok");
    }
  });

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
      setStatus("Service workers are unavailable in this browser profile.", "error");
      return;
    }
    try {
      await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      if (!isStandalone) {
        setStatus(
          isVivaldi
            ? "For Android Share, install from Chrome — not Vivaldi."
            : "Service worker ready. Install via Chrome for Share support.",
          isVivaldi ? "warn" : "ok",
        );
      }
    } catch (error) {
      setStatus(`Service worker failed: ${error.message || "registration error"}`, "error");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", registerServiceWorker, { once: true });
  } else {
    registerServiceWorker();
  }

  async function submitShare(formData) {
    const response = await fetch(shareUrl, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      redirect: "follow",
    });
    if (response.redirected) {
      window.location.assign(response.url);
      return;
    }
    if (response.ok) window.location.reload();
  }

  if ("launchQueue" in window) {
    window.launchQueue.setConsumer(async (launchParams) => {
      if (launchParams.targetURL) {
        window.location.assign(launchParams.targetURL);
        return;
      }

      const files = launchParams.files;
      if (!files?.length) return;

      const formData = new FormData();
      for (const handle of files) {
        formData.append("files", await handle.getFile());
      }
      await submitShare(formData);
    });
  }

  window.papShare = async function papShare(data) {
    if (!navigator.share) return false;
    try {
      await navigator.share(data);
      return true;
    } catch (error) {
      if (error?.name === "AbortError") return true;
      return false;
    }
  };
})();
