window.EFX = {
  toggleTheme(){
    const root = document.documentElement;
    const current = root.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("efx-theme", next);
  }
};

(function(){
  const saved = localStorage.getItem("efx-theme");
  if(saved){
    document.documentElement.setAttribute("data-theme", saved);
  }
})();
window.EFX = window.EFX || {};

EFX.isLoggedIn = function () {
  // acepta cualquiera de estos tokens (por si has cambiado nombres antes)
  const t =
    localStorage.getItem("token") ||
    localStorage.getItem("access_token") ||
    localStorage.getItem("jwt") ||
    sessionStorage.getItem("token") ||
    sessionStorage.getItem("access_token");
  return !!(t && String(t).length > 10);
};

EFX.requireLogin = function (nextUrl) {
  const url = "/static/usuarios.html#login" + (nextUrl ? `?next=${encodeURIComponent(nextUrl)}` : "");
  location.href = url;
};

