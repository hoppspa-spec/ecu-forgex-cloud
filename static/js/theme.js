// EFX Theme Toggle — persistente en localStorage
(() => {
  const KEY = "efx_theme";
  const root = document.documentElement;

  // default: dark (sin atributo)
  const saved = localStorage.getItem(KEY);
  if (saved === "light") root.setAttribute("data-theme", "light");

  // opcional: si quieres respetar preferencia del sistema SOLO cuando no hay guardado:
  if (!saved && window.matchMedia) {
    const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
    if (prefersLight) root.setAttribute("data-theme", "light");
  }

  window.EFX = window.EFX || {};
  window.EFX.toggleTheme = () => {
    const cur = root.getAttribute("data-theme") === "light" ? "light" : "dark";
    const next = cur === "light" ? "dark" : "light";
    if (next === "light") root.setAttribute("data-theme", "light");
    else root.removeAttribute("data-theme");
    localStorage.setItem(KEY, next);
    return next;
  };
})();
