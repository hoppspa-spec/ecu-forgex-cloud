// static/js/index.js
(() => {
  // ====== AUTH (DEMO) ======
  const TOKEN_KEY = "EFX_TOKEN";
  let TOKEN = localStorage.getItem(TOKEN_KEY) || null;

  const $ = (q, el = document) => el.querySelector(q);

  const btnLogin  = $("#btnLogin");
  const btnLogout = $("#btnLogout");

  function setAuthUi() {
    if (!btnLogin || !btnLogout) return;
    btnLogin.style.display  = TOKEN ? "none" : "inline-block";
    btnLogout.style.display = TOKEN ? "inline-block" : "none";
  }

  // Login DEMO: guarda un token cualquiera para destrabar "modo sesión"
  btnLogin?.addEventListener("click", () => {
    TOKEN = "demo-token-" + Date.now();
    localStorage.setItem(TOKEN_KEY, TOKEN);
    alert("✅ Sesión DEMO iniciada");
    setAuthUi();
  });

  btnLogout?.addEventListener("click", () => {
    TOKEN = null;
    localStorage.removeItem(TOKEN_KEY);
    alert("👋 Sesión cerrada");
    setAuthUi();
  });

  // ====== ESTADO ======
  let lastFile = null;
  let lastCvn = null;
  let lastAnalysis = null;
  let engineDetected = "auto";

  const yamlBox   = $("#yamlBox");
  const ecuInfo   = $("#ecuInfo");
  const patchList = $("#patchList");

  // selects
  const selBrand = $("#selBrand");
  const selModel = $("#selModel");
  const selYear  = $("#selYear");

  // ====== VEHÍCULOS (DEMO) ======
  const VEH = {
    brands: [
      {
        key: "maxus",
        label: "Maxus",
        models: [{ key: "t60", label: "T60 (LDV T60)", years: ["2017-2022"] }],
      },
    ],
  };

  function fillBrands() {
    if (!selBrand || !selModel || !selYear) return;

    selBrand.innerHTML = `<option value="">— Selecciona —</option>`;
    VEH.brands.forEach((b) => selBrand.append(new Option(b.label, b.key)));

    selModel.innerHTML = `<option value="">— Selecciona —</option>`;
    selYear.innerHTML  = `<option value="">— Selecciona —</option>`;
    selModel.disabled = true;
    selYear.disabled  = true;

    selBrand.onchange = () => {
      const brand = VEH.brands.find((b) => b.key === selBrand.value);

      selModel.innerHTML = `<option value="">— Selecciona —</option>`;
      selYear.innerHTML  = `<option value="">— Selecciona —</option>`;
      selYear.disabled = true;

      if (!brand) {
        selModel.disabled = true;
        updateYaml(); // refresca YAML
        return;
      }

      brand.models.forEach((m) => selModel.append(new Option(m.label, m.key)));
      selModel.disabled = false;
      updateYaml();
    };

    selModel.onchange = () => {
      const brand = VEH.brands.find((b) => b.key === selBrand.value);
      const model = brand?.models.find((m) => m.key === selModel.value);

      selYear.innerHTML = `<option value="">— Selecciona —</option>`;

      if (!model) {
        selYear.disabled = true;
        updateYaml();
        return;
      }

      model.years.forEach((y) => selYear.append(new Option(y, y)));
      selYear.disabled = false;
      updateYaml();
    };

    selYear.onchange = () => updateYaml();
  }

  function getVehicleSelection() {
    const brandObj = VEH.brands.find(b => b.key === (selBrand?.value || ""));
    const modelObj = brandObj?.models?.find(m => m.key === (selModel?.value || ""));
    return {
      brand: brandObj?.label || null,
      model: modelObj?.label || null,
      year: selYear?.value || null,
    };
  }

  // ====== YAML ======
  function toYaml(obj, indent = 0) {
    const pad = "  ".repeat(indent);
    if (obj === null || obj === undefined) return "null";
    if (Array.isArray(obj)) {
      if (!obj.length) return "[]";
      return obj.map(x => `${pad}- ${typeof x === "object" ? "\n" + toYaml(x, indent + 1) : String(x)}`).join("\n");
    }
    if (typeof obj !== "object") return String(obj);

    const out = [];
    for (const k of Object.keys(obj)) {
      const v = obj[k];
      if (typeof v === "object" && v !== null) {
        out.push(`${pad}${k}:`);
        out.push(toYaml(v, indent + 1));
      } else {
        out.push(`${pad}${k}: ${v === "" ? "null" : v}`);
      }
    }
    return out.join("\n");
  }

  function updateYaml(patch) {
    const veh = getVehicleSelection();
    const data = {
      vehicle: {
        brand: veh.brand,
        model: veh.model,
        year: veh.year,
      },
      ecu: {
        type: lastAnalysis?.ecu_type || null,
        part_number: lastAnalysis?.ecu_part_number || null,
      },
      file: {
        name: lastAnalysis?.filename || lastFile?.name || null,
        size_bytes: lastAnalysis?.bin_size || lastFile?.size || null,
        cvn_crc32: lastCvn || lastAnalysis?.cvn_crc32 || null,
      },
      patch: patch || { status: "not_selected" },
    };
    if (yamlBox) yamlBox.textContent = toYaml(data);
  }

  // ====== ECU INFO ======
  function renderEcuInfo() {
    if (!ecuInfo) return;
    if (!lastAnalysis) {
      ecuInfo.innerHTML = `<div>Esperando análisis…</div>`;
      return;
    }
    ecuInfo.innerHTML = `
      <div><strong>ECU Type:</strong> ${lastAnalysis.ecu_type || "—"}</div>
      <div><strong>Motor:</strong> ${engineDetected || "—"}</div>
      <div><strong>File size:</strong> ${lastAnalysis.bin_size || 0} bytes</div>
      <div><strong>CVN/CRC32:</strong> ${(lastAnalysis.cvn_crc32 || lastCvn || "—")}</div>
    `;
  }

  // ====== PATCHES (REAL: vienen desde backend) ======
  function renderPatches(recipes) {
    if (!patchList) return;

    if (!recipes || !recipes.length) {
      patchList.innerHTML = `<div class="patch"><div class="title">No hay parches disponibles</div></div>`;
      return;
    }

    patchList.innerHTML = "";
    recipes.forEach((p) => {
      const price = (typeof p.price === "number") ? ` — $${p.price}` : "";
      const el = document.createElement("div");
      el.className = "patch";
      el.innerHTML = `
        <div class="title">${p.label || p.id}${price}</div>
        <div class="kv"><small class="muted">ID:</small> ${p.id}</div>
        <button class="btn" style="margin-top:6px">Aplicar / Comprar</button>
      `;

      el.querySelector("button").addEventListener("click", async () => {
        // YAML “selected”
        updateYaml({
          status: "selected",
          id: p.id,
          label: p.label || p.id,
          price_usd: typeof p.price === "number" ? p.price : null,
        });

        // Crear orden y mandar a checkout
        await createOrderAndGo(p.id);
      });

      patchList.appendChild(el);
    });
  }

  async function loadFamilyPatches(family, engine) {
    if (!patchList) return;
    patchList.innerHTML = `<div class="patch"><div class="title">Cargando parches…</div></div>`;
    try {
      const url = `/public/recipes/${encodeURIComponent(family)}?engine=${encodeURIComponent(engine || "auto")}`;
      const r = await fetch(url, { cache: "no-store" });
      if (!r.ok) {
        renderPatches([]);
        return;
      }
      const d = await r.json();
      renderPatches(d.recipes || []);
    } catch {
      renderPatches([]);
    }
  }

  // ====== ORDER -> CHECKOUT ======
  async function createOrderAndGo(patchId) {
    if (!lastAnalysis?.analysis_id) {
      alert("Analiza un BIN primero.");
      return;
    }

    try {
      const r = await fetch("/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // DEMO: si el backend ignora auth, esto no estorba
          "Authorization": "Bearer " + (TOKEN || "")
        },
        body: JSON.stringify({
          analysis_id: lastAnalysis.analysis_id,
          patch_option_id: patchId,
        }),
      });

      if (!r.ok) {
        const t = await r.text().catch(() => "(sin detalle)");
        alert("No se pudo crear la orden:\n" + t);
        return;
      }

      const o = await r.json();
      if (!o.checkout_url) {
        alert("Orden creada, pero no llegó checkout_url");
        return;
      }
      location.href = o.checkout_url;
    } catch {
      alert("Error de red creando orden.");
    }
  }

  // ====== CRC32 ======
  function crc32(buf) {
    let c = 0xffffffff;
    for (let i = 0; i < buf.length; i++) {
      c ^= buf[i];
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    return (c ^ 0xffffffff) >>> 0;
  }

  $("#binfile")?.addEventListener("change", async (e) => {
    lastFile = e.target.files?.[0] || null;
    if (!lastFile) return;
    const buf = new Uint8Array(await lastFile.arrayBuffer());
    lastCvn = crc32(buf).toString(16).toUpperCase().padStart(8, "0");
    updateYaml(); // refresca YAML con file/cvn
  });

  // ====== ANALIZAR BIN ======
  $("#btnAnalizar")?.addEventListener("click", async () => {
    if (!lastFile) return alert("Selecciona un BIN");

    const fd = new FormData();
    fd.append("bin_file", lastFile);

    let r;
    try {
      r = await fetch("/analyze_bin", { method: "POST", body: fd });
    } catch {
      alert("Error de red en /analyze_bin");
      return;
    }

    if (!r.ok) {
      const t = await r.text().catch(()=>"(sin detalle)");
      alert("No se pudo analizar el BIN:\n" + t);
      return;
    }

    lastAnalysis = await r.json();

    engineDetected = /EDC|DCM|MD1/i.test(lastAnalysis.ecu_type || "")
      ? "diesel"
      : "petrol";

    renderEcuInfo();
    updateYaml({ status: "not_selected" });

    // ✅ CARGA PATCHES REALES DESDE BACKEND
    await loadFamilyPatches(lastAnalysis.ecu_type || "EDC17C81", engineDetected);
  });

  // ====== COPY YAML ======
  $("#btnCopyYaml")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(yamlBox?.textContent || "");
      alert("YAML copiado ✅");
    } catch {
      alert("No se pudo copiar.");
    }
  });

  // ====== INIT ======
  fillBrands();
  setAuthUi();
  renderEcuInfo();
  updateYaml();
})();
