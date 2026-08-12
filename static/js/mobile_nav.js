document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const toggle = document.getElementById("mobile-menu-toggle");
  const closeBtn = document.getElementById("mobile-menu-close");
  const menu = document.getElementById("mobile-menu");
  const backdrop = document.getElementById("mobile-menu-backdrop");
  const form = document.getElementById("mobile-ticker-search");
  const input = document.getElementById("mobile-ticker-input");

  const openMenu = () => {
    if (!menu || !backdrop || !toggle) return;
    body.classList.add("mobile-nav-open");
    backdrop.hidden = false;
    menu.setAttribute("aria-hidden", "false");
    toggle.setAttribute("aria-expanded", "true");
  };

  const closeMenu = () => {
    if (!menu || !backdrop || !toggle) return;
    body.classList.remove("mobile-nav-open");
    backdrop.hidden = true;
    menu.setAttribute("aria-hidden", "true");
    toggle.setAttribute("aria-expanded", "false");
  };

  toggle?.addEventListener("click", () => {
    if (body.classList.contains("mobile-nav-open")) closeMenu();
    else openMenu();
  });
  closeBtn?.addEventListener("click", closeMenu);
  backdrop?.addEventListener("click", closeMenu);
  document.querySelectorAll(".mobile-menu-links a").forEach(a => a.addEventListener("click", closeMenu));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeMenu();
  });

  form?.addEventListener("submit", e => {
    e.preventDefault();
    const symbol = (input?.value || "").trim().toUpperCase();
    if (!symbol) return;
    closeMenu();
    window.location.href = `/stock/${encodeURIComponent(symbol)}`;
  });
});
