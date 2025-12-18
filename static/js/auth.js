// static/js/auth.js
window.EFX = window.EFX || {};

EFX.tokenKey = "efx_token";

EFX.getToken = () => localStorage.getItem(EFX.tokenKey) || "";
EFX.setToken = (t) => localStorage.setItem(EFX.tokenKey, t);
EFX.clearToken = () => localStorage.removeItem(EFX.tokenKey);

EFX.isLogged = () => !!EFX.getToken();

EFX.authFetch = async (url, opts = {}) => {
  const t = EFX.getToken();
  const headers = Object.assign({}, opts.headers || {});
  if (t) headers["Authorization"] = "Bearer " + t;
  return fetch(url, { ...opts, headers });
};

EFX.applyHeaderAuth = () => {
  const btnLogin = document.getElementById("btnLogin");
  const btnRegister = document.getElementById("btnRegister");
  const btnLogout = document.getElementById("btnLogout");

  if (!btnLogin || !btnRegister || !btnLogout) return;

  if (EFX.isLogged()) {
    btnLogin.style.display = "none";
    btnRegister.style.display = "none";
    btnLogout.style.display = "";
  } else {
    btnLogin.style.display = "";
    btnRegister.style.display = "";
    btnLogout.style.display = "none";
  }
};

EFX.logout = () => {
  EFX.clearToken();
  location.href = "/static/index.html";
};

// util next=
EFX.getNext = () => {
  const u = new URL(location.href);
  return u.searchParams.get("next") || "/static/index.html";
};
