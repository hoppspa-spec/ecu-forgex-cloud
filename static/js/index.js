// static/js/index.js
(() => {
  const ADMIN_EMAIL = "demo@ecuforge.dev"; // <- cambia por el tuyo si quieres
  let TOKEN = localStorage.getItem("EFX_TOKEN") || null;
  let CURRENT_USER = null;

  let lastFile = null;
  let lastCvn = null;
  let lastAnalysis = null;
  let engineDetected = "auto";

  const $ = (q, el=document) => el.querySelector(q);
  const yamlBox = $("#yamlBox");
  const ecuInfo = $("#ecuInfo");
  const patchList = $("#patchList");
  const debugBox = $("#debugBox");
  const debugContent = $("#debugContent");

  const btnLogin = $("#btnLogin");
  const btnLogout = $("#btnLogout");

  // --- Auth UI (dummy: muestra/oculta botones; usa /users/me si existe)
  async function fetchMe(){
    if(!TOKEN) return null;
    try{
      const r = await fetch("/users/me", { headers: { "Authorization":"Bearer "+TOKEN }});
      if(!r.ok) return null;
      return await r.json();
    }catch{ return null; }
  }
  function setAuthUi(on){
    btnLogin.style.display = on? "none":"inline-block";
    btnLogout.style.display = on? "inline-block":"none";
  }
  btnLogin.onclick = () => alert("Para el modo prueba, puedes usar tu login normal. (Este botón sólo cambia visibilidad).");
  btnLogout.onclick = () => { TOKEN=null; localStorage.removeItem("EFX_TOKEN"); setAuthUi(false); location.reload(); };

  // --- Carga marcas/modelos/años mínimo (placeholder, no bloquea nada)
  const VEH = {
    brands: [
      { key:"maxus", label:"Maxus", models:[
        { key:"t60", label:"T60 (LDV T60)", years:["2017-2022"] }
      ] }
    ]
  };
  function fillBrands(){
    const selBrand = $("#selBrand");
    selBrand.innerHTML = '<option value="">— Selecciona —</option>';
    VEH.brands.forEach(b => selBrand.append(new Option(b.label,b.key)));
    $("#selModel").disabled = true; $("#selYear").disabled = true;
    selBrand.onchange = () => {
      const b = VEH.brands.find(x=>x.key===selBrand.value);
      const selModel = $("#selModel");
      selModel.innerHTML = '<option value="">— Selecciona —</option>';
      (b?.models||[]).forEach(m=>selModel.append(new Option(m.label,m.key)));
      selModel.disabled = !b;
      $("#selYear").innerHTML = '<option value="">— Selecciona —</option>';
      $("#selYear").disabled = true;
    };
    $("#selModel").onchange = ()=>{
      const b = VEH.brands.find(x=>x.key===$("#selBrand").value);
      const m = (b?.models||[]).find(x=>x.key===$("#selModel").value);
      const selYear = $("#selYear");
      selYear.innerHTML = '<option value="">— Selecciona —</option>';
      (m?.years||[]).forEach(y=>selYear.append(new Option(y,y)));
      selYear.disabled = !m;
    };
  }

  // --- Utiles
  function toYaml(obj, indent=0){
    const pad = '  '.repeat(indent);
    if (obj==null) return 'null';
    if (Array.isArray(obj)){
      return obj.length
        ? obj.map(x=>`${pad}- ${typeof x==='object' ? '\n'+toYaml(x,indent+1) : String(x)}`).join('\n')
        : '[]';
    }
    if (typeof obj==='object'){
      const lines=[];
      for(const k of Object.keys(obj)){
        const v=obj[k];
        if (v && typeof v==='object' && !Array.isArray(v)){ lines.push(`${pad}${k}:`); lines.push(toYaml(v,indent+1)); }
        else if (Array.isArray(v)){ lines.push(`${pad}${k}:`); lines.push(v.length? toYaml(v,indent+1) : pad+'  []'); }
        else { lines.push(`${pad}${k}: ${v==null||v===''? 'null' : String(v)}`); }
      }
      return lines.join('\n');
    }
    return String(obj);
  }
  function updateYaml({patch}){
    const obj = {
      ecu: {
        type: lastAnalysis?.ecu_type || null,
        part_number: lastAnalysis?.ecu_part_number || null
      },
      file: {
        name: lastAnalysis?.filename || lastFile?.name || null,
        size_bytes: lastAnalysis?.bin_size || lastFile?.size || null,
        cvn_crc32: lastCvn || null
      },
      patch: patch || { status:"not_selected" }
    };
    yamlBox.textContent = toYaml(obj);
  }
  function setEcuInfoHtml(){
    const ecu = lastAnalysis?.ecu_type || "Desconocida";
    const pn  = lastAnalysis?.ecu_part_number || "—";
    const size = new Intl.NumberFormat('es-CL').format(lastAnalysis?.bin_size||0);
    const motor = engineDetected;
    ecuInfo.innerHTML = `
      <div><strong>ECU Type:</strong> ${ecu}</div>
      <div><strong>Part Number:</strong> ${pn}</div>
      <div><strong>File size:</strong> ${size} bytes</div>
      <div><strong>Motor:</strong> ${motor}</div>
    `;
  }
  function renderPatches(items){
    if(!items || !items.length){
      patchList.innerHTML = `<div class="patch"><div class="title">No hay parches disponibles</div></div>`;
      return;
    }
    patchList.innerHTML = "";
    items.forEach(p=>{
      const price = (typeof p.price==="number") ? ` — $${p.price}` : "";
      const el = document.createElement("div");
      el.className = "patch";
      el.innerHTML = `
        <div class="title">${p.label}${price}</div>
        <div class="kv"><div><small class="muted">ID:</small> ${p.id}</div></div>
        <div style="margin-top:6px">
          <button class="btn" data-id="${p.id}">Aplicar / Comprar</button>
        </div>
      `;
      el.querySelector("button").onclick = ()=> {
        updateYaml({patch: { status:"selected", id:p.id, label:p.label, price_usd:p.price ?? null }});
        alert(`Seleccionado: ${p.label}`);
      };
      patchList.appendChild(el);
    });
  }

  // --- CRC32 (para CVN demo)
  (function(){
    const table = new Uint32Array(256).map((_,n)=>{let c=n; for(let k=0;k<8;k++) c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1); return c>>>0;});
    window.crc32 = (buf)=>{ let c=0^(-1); for(let i=0;i<buf.length;i++) c=(c>>>8)^table[(c^buf[i])&0xFF]; return (c^(-1))>>>0; };
  })();

  // --- BIN change
  $("#binfile").addEventListener("change", async (e)=>{
    lastFile = e.target.files?.[0] || null;
    if(lastFile){
      const buf = new Uint8Array(await lastFile.arrayBuffer());
      lastCvn = crc32(buf).toString(16).toUpperCase().padStart(8,'0');
    }
  });

  // --- Analizar BIN (modo prueba compatible con tu backend actual)
  $("#btnAnalizar").onclick = async ()=>{
    const f = $("#binfile").files[0];
    if(!f){ alert("Selecciona un BIN"); return; }
    if(!/\.(bin|mpc|org|e2p|101)$/i.test(f.name||"")){ alert("Formato no soportado."); return; }

    const fd = new FormData(); fd.append("bin_file", f);
    let r;
    try{
      r = await fetch("/analyze_bin",{method:"POST",body:fd});
    }catch(e){
      alert("Error de red en /analyze_bin"); return;
    }
    if(!r.ok){
      const t = await r.text().catch(()=>"(sin detalle)");
      alert("No se pudo analizar el BIN. HTTP "+r.status+"\n"+t); return;
    }
    const data = await r.json();
    lastAnalysis = data;

    // motor por heurística simple
    if(/EDC|MD1|MJD|DCM|SID/i.test(data.ecu_type||"")) engineDetected="diesel";
    else if(/MED|MG1|MEVD|ME7/i.test(data.ecu_type||"")) engineDetected="petrol";
    else engineDetected="auto";

    setEcuInfoHtml();
    updateYaml({patch:{status:"not_selected"}});

    // === MODO PRUEBA: Forzamos familia EDC17C81 (siempre)
    await loadFamilyPatches("EDC17C81", engineDetected);
  };

  async function loadFamilyPatches(family, engine){
    try{
      const url = `/public/recipes/${encodeURIComponent(family)}?engine=${encodeURIComponent(engine||"auto")}`;
      const r = await fetch(url);
      if(!r.ok){ renderPatches([]); return; }
      const d = await r.json();
      renderPatches(d.recipes||[]);
    }catch{
      renderPatches([]);
    }
  }

  // --- Copiar YAML
  $("#btnCopyYaml")?.addEventListener("click", async ()=>{
    try{ await navigator.clipboard.writeText(yamlBox.textContent||''); alert('YAML copiado.'); }
    catch{ alert("No se pudo copiar."); }
  });

  // --- Init
  (async function init(){
    fillBrands();
    setAuthUi(!!TOKEN);
    CURRENT_USER = await fetchMe();
    const isAdmin = !!CURRENT_USER && (CURRENT_USER.email || CURRENT_USER.username || "").toLowerCase() === ADMIN_EMAIL.toLowerCase();
    if(isAdmin){ debugBox.style.display="block"; debugContent.innerHTML = `<small class="muted">Listo para mostrar offsets obtenidos del análisis</small>`; }
  })();
})();
