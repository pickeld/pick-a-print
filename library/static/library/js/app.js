document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  if (!toggle || !sidebar || !overlay) return;

  const open = () => {
    sidebar.classList.add("open");
    overlay.classList.add("open");
    document.body.classList.add("nav-open");
  };

  const close = () => {
    sidebar.classList.remove("open");
    overlay.classList.remove("open");
    document.body.classList.remove("nav-open");
  };

  toggle.addEventListener("click", () => {
    if (sidebar.classList.contains("open")) close();
    else open();
  });

  overlay.addEventListener("click", close);
  sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
});
