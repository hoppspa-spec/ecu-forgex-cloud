// static/js/index.js
(() => {
  let lastFile = null;
  let lastCvn = null;
  let lastAnalysis = null;
  let engineDetected = "auto";

  const $ = (q) => document.querySelector(q);
  const yamlBox = $("#yamlBox");
  const ecuInfo = $("#ecuInfo");
  const patchList = $("#patchList");

  const btnLogin  = $("#btnLogin");
  const btnLogout = $("#btnLogout");

  const TOKEN_KEY = "EFX_TOKEN";
  let TOKEN = localStorage.getItem(TOKEN_KEY) || null;

  function setAuthUi(){
    if(btnLogin)  btnLogin.style.display  = TOKEN ? "none" : "inline-block";
    if(btnLogout) btnLogout.style.display = TOKEN ? "inline-block" : "none";
  }

  // ✅ LOGIN DEMO (desbloquea checkout)
  btnLogin?.addEventListener("click", () => {
    TOKEN = "demo-token";
    localStorage.setItem(TOKEN_KEY, TOKEN);
    alert("Sesión DEMO iniciada ✅");
    setAuthUi();
  });

  btnLogout?.addEventListener("click", () => {
    TOKEN = null;
    localStorage.removeItem(TOKEN_KEY);
    alert("Sesión cerrada.");
    setAuthUi();
  });

  /* ==========================
     VEHÍCULOS (FIX: habilitar selects)
     ========================== */
  const VEH = {
    brands: [
      { key:"maxus", label:"Maxus", models:[
        { key:"t60", label:"T60 (LDV T60)", years:["2017-2022"] }
      ]}
    ]
  };

  function fillBrands(){
    const selBrand = $("#selBrand");
    const selModel = $("#selModel");
    const selYear  = $("#selYear");
    if(!selBrand || !selModel || !selYear) return;

    selModel.disabled = true;
    selYear.disabled  = true;

    selBrand.innerHTML = `<option value="">— Selecciona —</option>`;
    VEH.brands.forEach(b => selBrand.append(new Option(b.label, b.key)));

    selBrand.onchange = () => {
      const b = VEH.brands.find(x => x.key === selBrand.value);

      selModel.innerHTML = `<option value="">— Selecciona —</option>`;
      selYear.innerHTML  = `<option value="">— Selecciona —</option>`;
      selYear.disabled   = true;

      if(!b){
        selModel.disabled = true;
        return;
      }

      selModel.disabled = false;
      b.models.forEach(m => selModel.append(new Option(m.label, m.key)));
    };

    selModel.onchange = () => {
      const b = VEH.brands.find(x => x.key === selBrand.value);
      const m = b?.models.find(x => x.key === selModel.value);

      selYear.innerHTML = `<option value="">— Selecciona —</option>`;
      if(!m){
        selYear.disabled = true;
        return;
      }
      selYear.disabled = false;
      m.years.forEach(y => selYear.append(new Option(y, y)));
    };
  }

  /* ==========================
     YAML
     ========================== */
  function toYaml(obj, indent=0){
    const pad="  ".repeat(indent);
    if(obj===null) return "null";
    if(typeof obj!=="object") return String(obj);
    let out=[];
    for(const k in obj){
      const v=obj[k];
      if(typeof v==="object" && v!==null){
        out.push(`${pad}${k}:`);
        out.push(toYaml(v, indent+1));
      } else out.push(`${pad}${k}: ${v}`);
    }
    return out.join("\n");
  }

  function updateYaml(patch){
    const data = {
      ecu:{ type:lastAnalysis?.ecu_type||null, part_number:lastAnalysis?.ecu_part_number||null },
      file:{ name:lastFile?.name||null, size_bytes:lastFile?.size||null, cvn_crc32:lastCvn||null },
      patch: patch || { status:"not_selected" }
    };
    yamlBox.textContent = toYaml(data);
  }

  /* ==========================
     ECU INFO
     ========================== */
  function renderEcuInfo(){
    ecuInfo.innerHTML = `
      <div><strong>ECU Type:</strong> ${lastAnalysis.ecu_type}</div>
      <div><strong>Motor:</strong> ${engineDetected}</div>
      <div><strong>File size:</strong> ${lastAnalysis.bin_size} bytes</div>
    `;
  }

  /* ==========================
     PATCHES (demo)
     ========================== */
  function renderPatches(ecu){
    patchList.innerHTML = "";
    if(!ecu){
      patchList.innerHTML = `<div class="patch"><div class="title">No hay parches disponibles</div></div>`;
      return;
    }

    patchList.innerHTML = `
      <div class="patch">
        <div class="title">DPF OFF — ${ecu} (diesel) — $59</div>
        <button id="btnBuy" class="btn">Aplicar / Comprar</button>
      </div>
    `;

    $("#btnBuy").onclick = async () => {
      if(!TOKEN){
        alert("Primero inicia sesión (demo) para comprar.");
        return;
      }
      if(!lastAnalysis?.analysis_id){
        alert("Analiza un BIN primero.");
        return;
      }

      updateYaml({status:"selected", id:"dpf_off", label:"DPF OFF", price_usd:59});

      // ✅ crea orden y te manda al checkout
      const r = await fetch("/orders", {
        method:"POST",
        headers:{
          "Authorization":"Bearer " + TOKEN,
          "Content-Type":"application/json"
        },
        body: JSON.stringify({
          analysis_id: lastAnalysis.analysis_id,
          patch_option_id: "dpf_off"
        })
      });

      if(!r.ok){
        const t = await r.text().catch(()=>"(sin detalle)");
        alert("Error creando orden:\n" + t);
        return;
      }

      const o = await r.json();
      location.href = o.checkout_url;
    };
  }

  /* ==========================
     CRC32 local (solo display)
     ========================== */
  function crc32(buf){
    let c=0xffffffff;
    for(let i=0;i<buf.length;i++){
      c^=buf[i];
      for(let k=0;k<8;k++) c = c&1 ? (0xedb88320^(c>>>1)) : (c>>>1);
    }
    return (c^0xffffffff)>>>0;
  }

  $("#binfile").addEventListener("change", async (e)=>{
    lastFile = e.target.files?.[0] || null;
    if(!lastFile) return;
    const buf = new Uint8Array(await lastFile.arrayBuffer());
    lastCvn = crc32(buf).toString(16).toUpperCase().padStart(8,"0");
    updateYaml();
  });

  /* ==========================
     ANALIZAR BIN
     ========================== */
  $("#btnAnalizar").onclick = async () => {
    if(!lastFile) return alert("Selecciona un BIN");

    const fd = new FormData();
    fd.append("bin_file", lastFile);

    const r = await fetch("/analyze_bin", { method:"POST", body: fd });
    if(!r.ok) return alert("No se pudo analizar el BIN");

    lastAnalysis = await r.json();

    engineDetected = /EDC|DCM|MD1/i.test(lastAnalysis.ecu_type || "")
      ? "diesel"
      : "petrol";

    renderEcuInfo();
    renderPatches(lastAnalysis.ecu_type);
    updateYaml({status:"not_selected"});
  };

  // INIT
  fillBrands();
  setAuthUi();
  updateYaml();
})();
