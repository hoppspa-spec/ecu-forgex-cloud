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

  // Login DEMO: guarda un token cualquiera para destrabar checkout
  btnLogin?.addEventListener("click", () => {
    // si quieres, cámbialo por un prompt email/pass
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

  const yamlBox  = $("#yamlBox");
  const ecuInfo  = $("#ecuInfo");
  const patchList = $("#patchList");

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
    const selBrand = $("#selBrand");
    const selModel = $("#selModel");
    const selYear  = $("#selYear");

    if (!selBrand || !selModel || !selYear) return;

    // estado inicial
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
        return;
      }

      brand.models.forEach((m) => selModel.append(new Option(m.label, m.key)));
      selModel.disabled = false; // ✅ habilitar
    };

    selModel.onchange = () => {
      const brand = VEH.brands.find((b) => b.key === selBrand.value);
      const model = brand?.models.find((m) => m.key === selModel.value);

      selYear.innerHTML = `<option value="">— Selecciona —</option>`;

      if (!model) {
        selYear.disabled = true;
        return;
      }

      model.years.forEach((y) => selYear.append(new Option(y, y)));
      selYear.disabled = false; // ✅ habilitar
    };
  }

  // ====== YAML ======
  function toYaml(obj, indent = 0) {
    const pad = "  ".repeat(indent);
    if (obj === null) return "null";
    if (typeof obj !== "object") return String(obj);

    const out = [];
    for (const k in obj) {
      const v = obj[k];
      if (typeof v === "object" && v !== null) {
        out.push(`${pad}${k}:`);
        out.push(toYaml(v, indent + 1));
      } else {
        out.push(`${pad}${k}: ${v}`);
      }
    }
    return out.join("\n");
  }

  function updateYaml(patch) {
    const data = {
      ecu: {
        type: lastAnalysis?.ecu_type || null,
        part_number: lastAnalysis?.ecu_part_number || null,
      },
      file: {
        name: lastFile?.name || null,
        size_bytes: lastFile?.size || null,
        cvn_crc32: lastCvn || null,
      },
      patch: patch || { status: "not_selected" },
    };
    if (yamlBox) yamlBox.textContent = toYaml(data);
  }

  // ====== ECU INFO ======
  function renderEcuInfo() {
    if (!ecuInfo || !lastAnalysis) return;
    ecuInfo.innerHTML = `
      <div><strong>ECU Type:</strong> ${lastAnalysis.ecu_type}</div>
      <div><strong>Motor:</strong> ${engineDetected}</div>
      <div><strong>File size:</strong> ${lastAnalysis.bin_size} bytes</div>
    `;
  }

  // ====== PATCHES (DEMO) ======
  function renderPatches(ecu) {
    if (!patchList) return;

    patchList.innerHTML = "";
    if (!ecu) {
      patchList.innerHTML = `<div class="patch"><div class="title">No hay parches disponibles</div></div>`;
      return;
    }

    patchList.innerHTML = `
      <div class="patch">
        <div class="title">DPF OFF — ${ecu} (diesel) — $59</div>
        <button class="btn" id="btnApplyPatch">Aplicar</button>
      </div>
    `;

    $("#btnApplyPatch")?.addEventListener("click", async () => {
      updateYaml({
        status: "selected",
        id: "dpf_off",
        label: "DPF OFF",
        price_usd: 59,
      });

      // ✅ crear orden demo y mandar a checkout
      try {
        const r = await fetch("/orders", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Authorization": "Bearer " + (TOKEN || "") },
          body: JSON.stringify({
            analysis_id: lastAnalysis?.analysis_id || "demo-analysis-001",
            patch_option_id: "dpf_off",
          }),
        });

        if (!r.ok) {
          const t = await r.text().catch(() => "(sin detalle)");
          alert("No se pudo crear la orden:\n" + t);
          return;
        }

        const o = await r.json();
        alert("✅ Orden creada (demo). Vamos a checkout.");
        location.href = o.checkout_url; // /static/checkout.html?order_id=...
      } catch (e) {
        alert("Error de red creando orden.");
      }
    });
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
  });

  // ====== ANALIZAR BIN ======
  $("#btnAnalizar")?.addEventListener("click", async () => {
    if (!lastFile) return alert("Selecciona un BIN");

    const fd = new FormData();
    fd.append("bin_file", lastFile);

    const r = await fetch("/analyze_bin", { method: "POST", body: fd });
    if (!r.ok) return alert("No se pudo analizar el BIN");

    lastAnalysis = await r.json();

    engineDetected = /EDC|DCM|MD1/i.test(lastAnalysis.ecu_type) ? "diesel" : "petrol";

    renderEcuInfo();
    renderPatches(lastAnalysis.ecu_type);
    updateYaml();
  });

  // ====== INIT ======
  fillBrands();
  setAuthUi();
})();
