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
