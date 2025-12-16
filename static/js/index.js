// static/js/index.js
(() => {
  const ADMIN_EMAIL = "demo@ecuforge.dev";
  let TOKEN = localStorage.getItem("EFX_TOKEN") || null;
  let CURRENT_USER = null;

  let lastFile = null;
  let lastCvn = null;
  let lastAnalysis = null;
  let engineDetected = "auto";

  const $ = (q, el=document) => el.querySelector(q);
  const yamlBox = $("#yamlBox");
  const ecuInfo = $("#ecuInfo");
  const patchList = document.getElementById("patchList") || document.getElementById("patches-list");
  const debugBox = $("#debugBox");
  const debugContent = $("#debugContent");

  const btnLogin = $("#btnLogin");
  const btnLogout = $("#btnLogout");

  // ===== AUTH =====
  async function fetchMe(){
    if(!TOKEN) return null;
    try{
      const r = await fetch("/users/me",{headers:{"Authorization":"Bearer "+TOKEN}});
      if(!r.ok) return null;
      return await r.json();
    }catch{return null;}
  }
  function setAuthUi(on){
    if(btnLogin) btnLogin.style.display = on?"none":"inline-block";
    if(btnLogout) btnLogout.style.display = on?"inline-block":"none";
  }
  btnLogin?.addEventListener("click",()=>alert("Modo demo: usa tu login real"));
  btnLogout?.addEventListener("click",()=>{TOKEN=null;localStorage.removeItem("EFX_TOKEN");setAuthUi(false);location.reload();});

  // ===== UTIL =====
  function toYaml(obj, indent=0){
    const pad='  '.repeat(indent);
    if(obj==null) return 'null';
    if(Array.isArray(obj)){
      return obj.length? obj.map(x=>`${pad}- ${typeof x==='object' ? '\n'+toYaml(x,indent+1):String(x)}`).join('\n'):'[]';
    }
    if(typeof obj==='object'){
      const lines=[];
      for(const k of Object.keys(obj)){
        const v=obj[k];
        if(v&&typeof v==='object'&&!Array.isArray(v)){lines.push(`${pad}${k}:`);lines.push(toYaml(v,indent+1));}
        else if(Array.isArray(v)){lines.push(`${pad}${k}:`);lines.push(v.length?toYaml(v,indent+1):pad+'  []');}
        else{lines.push(`${pad}${k}: ${v==null||v===''?'null':String(v)}`);}
      }
      return lines.join('\n');
    }
    return String(obj);
  }
  function updateYaml({patch}){
    const obj = {
      ecu:{type:lastAnalysis?.ecu_type||null,part_number:lastAnalysis?.ecu_part_number||null},
      file:{name:lastAnalysis?.filename||lastFile?.name||null,size_bytes:lastAnalysis?.bin_size||lastFile?.size||null,cvn_crc32:lastCvn||null},
      patch:patch||{status:"not_selected"}
    };
    if(yamlBox) yamlBox.textContent = toYaml(obj);
  }
  function setEcuInfoHtml(){
    const ecu=lastAnalysis?.ecu_type||"Desconocida";
    const pn=lastAnalysis?.ecu_part_number||"—";
    const size=new Intl.NumberFormat('es-CL').format(lastAnalysis?.bin_size||0);
    const motor=engineDetected;
    ecuInfo.innerHTML=`
      <div><strong>ECU Type:</strong> ${ecu}</div>
      <div><strong>Part Number:</strong> ${pn}</div>
      <div><strong>File size:</strong> ${size} bytes</div>
      <div><strong>Motor:</strong> ${motor}</div>`;
  }

  // ===== COMPRA / ORDEN =====
  async function ensureAuth(){
    if(TOKEN){
      try{
        const r=await fetch("/users/me",{headers:{"Authorization":"Bearer "+TOKEN}});
        if(r.ok) return true;
      }catch{}
    }
    alert("Debes iniciar sesión para comprar.");
    location.href="/static/usuarios.html?next=/static/index.html";
    return false;
  }

  async function createOrder(patch){
    if(!(await ensureAuth())) return;
    if(!lastAnalysis?.analysis_id){alert("Analiza un BIN primero.");return;}
    try{
      const r=await fetch("/orders",{
        method:"POST",
        headers:{
          "Authorization":"Bearer "+TOKEN,
          "Content-Type":"application/json"
        },
        body:JSON.stringify({
          analysis_id:lastAnalysis.analysis_id,
          patch_option_id:patch.id
        })
      });
      if(!r.ok){
        const t=await r.text().catch(()=>"(sin detalle)");
        alert("Error creando la orden:\n"+t);
        return;
      }
      const d=await r.json();
      location.href=d.checkout_url||(`/static/checkout.html?order_id=${d.id}`);
    }catch{alert("Error de red creando orden.");}
  }

  // ===== PATCHES =====
  function renderPatches(items){
    if(!patchList) return;
    if(!items||!items.length){
      patchList.innerHTML=`<div class="patch"><div class="title">No hay parches disponibles</div></div>`;
      return;
    }
    patchList.innerHTML="";
    items.forEach(p=>{
      const price=(typeof p.price==="number")?` — $${p.price}`:(typeof p.price==="object"&&p.price?.USD!=null?` — $${p.price.USD}`:"");
      const el=document.createElement("div");
      el.className="patch";
      el.innerHTML=`
        <div class="title">${p.label}${price}</div>
        <div class="kv"><small>ID:</small> ${p.id}</div>
        <button class="btn" style="margin-top:6px">Aplicar / Comprar</button>`;
      el.querySelector("button").onclick=async()=>{
        updateYaml({patch:{status:"selected",id:p.id,label:p.label,price_usd:p.price?.USD||p.price||null}});
        await createOrder(p);
      };
      patchList.appendChild(el);
    });
  }

  async function loadFamilyPatches(family,engine){
    patchList.innerHTML=`<div class="patch"><div class="title">Cargando parches...</div></div>`;
    try{
      const r=await fetch(`/public/recipes/${encodeURIComponent(family)}?engine=${engine}`,{cache:"no-store"});
      if(r.ok){
        const d=await r.json();
        if(d.recipes?.length){renderPatches(d.recipes);return;}
      }
    }catch{}
    try{
      const g=await fetch("/static/patches/global.json",{cache:"no-store"});
      if(g.ok){
        const data=await g.json();
        const patches=(data.patches||[]).filter(p=>
          (p.compatible_ecu||[]).some(e=>String(e).toUpperCase()===String(family).toUpperCase())
        );
        renderPatches(patches);
        return;
      }
    }catch{}
    renderPatches([]);
  }

  // ===== ANALISIS BIN =====
  $("#binfile")?.addEventListener("change",async(e)=>{
    lastFile=e.target.files?.[0]||null;
    if(lastFile){
      const buf=new Uint8Array(await lastFile.arrayBuffer());
      lastCvn=(function crc32(buf){let c=0xffffffff;for(const b of buf)c=(c>>>8)^((()=>{let n=b;for(let k=0;k<8;k++)n=(n&1)?(0xEDB88320^(n>>>1)):(n>>>1);return n>>>0;})()[(c^b)&0xff]);return(c^(-1))>>>0;})(buf);
      lastCvn=lastCvn.toString(16).toUpperCase().padStart(8,"0");
    }
  });

  $("#btnAnalizar")?.addEventListener("click",async()=>{
    const f=$("#binfile")?.files?.[0];
    if(!f){alert("Selecciona un BIN");return;}
    if(!/\.(bin|mpc|org|e2p|101)$/i.test(f.name)){alert("Formato no soportado");return;}
    const fd=new FormData();fd.append("bin_file",f);
    let r;
    try{r=await fetch("/analyze_bin",{method:"POST",body:fd});}catch{alert("Error de red.");return;}
    if(!r.ok){alert("No se pudo analizar el BIN");return;}
    const data=await r.json();
    lastAnalysis=data;
    if(/EDC|MD1|MJD|DCM|SID/i.test(data.ecu_type||""))engineDetected="diesel";
    else if(/MED|MG1|MEVD|ME7/i.test(data.ecu_type||""))engineDetected="petrol";
    else engineDetected="auto";
    setEcuInfoHtml();
    updateYaml({patch:{status:"not_selected"}});
    await loadFamilyPatches(data.ecu_type||"EDC17C81",engineDetected);
  });

  // ===== COPY YAML =====
  $("#btnCopyYaml")?.addEventListener("click",async()=>{
    try{await navigator.clipboard.writeText(yamlBox.textContent||"");alert("YAML copiado");}
    catch{alert("No se pudo copiar");}
  });

  // ===== INIT =====
  (async()=>{
    setAuthUi(!!TOKEN);
    CURRENT_USER=await fetchMe();
    const isAdmin=!!CURRENT_USER&&(CURRENT_USER.email||"").toLowerCase()===ADMIN_EMAIL.toLowerCase();
    if(isAdmin&&debugBox){
      debugBox.style.display="block";
      debugContent.innerHTML=`<small class="muted">Debug activo</small>`;
    }
  })();
})();
