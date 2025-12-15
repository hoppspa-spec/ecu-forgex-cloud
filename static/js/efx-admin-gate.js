/* ===== Flags globales ===== */
window.__OWNER_EMAIL__ = "tu-email@tu-dominio.cl";   // cambia por tu correo real
window.__TEST_MODE__   = true;                       // modo prueba ON
window.__TEST_FAMILY__ = "EDC17C81";                 // familia foco

/* ===== Admin gate ===== */
(async function adminGate(){
  try{
    const token = localStorage.getItem("EFX_TOKEN");
    if(!token) return;
    const r = await fetch("/users/me", { headers:{ "Authorization":"Bearer "+token }});
    if(!r.ok) return;
    const me = await r.json();
    const isOwner = (me?.email||"").toLowerCase() === (window.__OWNER_EMAIL__||"").toLowerCase();
    document.documentElement.dataset.owner = isOwner ? "1" : "0";
    document.querySelectorAll(".admin-only").forEach(el=>{
      el.style.display = isOwner ? "" : "none";
    });
  }catch(_){}
})();
