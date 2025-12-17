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

  // ===== Vehículos demo =====
  const VEH = {
    brands: [
      {
        key: "maxus",
        label: "Maxus",
        models: [{ key: "t60", label: "T60 (LDV T60)", years: ["2017-2022"] }]
      }
    ]
  };

  function fillBrands() {
    const selBrand = $("#selBrand");
    const selModel = $("#selModel");
    const selYear = $("#selYear");

    selBrand.innerHTML = `<option value="">— Selecciona —</option>`;
    VEH.brands.forEach(b => selBrand.append(new Option(b.label, b.key)));

    // estado inicial
    selModel.disabled = true;
    selYear.disabled = true;

    selBrand.onchange = () => {
      const brand = VEH.brands.find(b => b.key === selBrand.value);

      selModel.innerHTML = `<option value="">— Selecciona —</option>`;
      selYear.innerHTML = `<option value="">— Selecciona —</option>`;
      selYear.disabled = true;

      if (!brand) {
        selModel.disabled = true;
        return;
      }

      brand.models.forEach(m => selModel.append(new Option(m.label, m.key)));
      selModel.disabled = false;
    };

    selModel.onchange = () => {
      const brand = VEH.brands.find(b => b.key === selBrand.value);
      const model = brand?.models.find(m => m.key === selModel.value);

      selYear.innerHTML = `<option value="">— Selecciona —</option>`;
      if (!model) {
        selYear.disabled = true;
        return;
      }

      model.years.forEach(y => selYear.append(new Option(y, y)));
      selYear.disabled = false;
    };
  }

  // ===== YAML =====
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
      vehicle: {
        brand: $("#selBrand")?.value || null,
        model: $("#selModel")?.value || null,
        year: $("#selYear")?.value || null,
      },
      ecu: {
        type: lastAnalysis?.ecu_type || null,
        part_number: lastAnalysis?.ecu_part_number || null
      },
      file: {
        name: lastFile?.name || null,
        size_bytes: lastFile?.size || null,
        cvn_crc32: lastCvn || null
      },
      patch: patch || { status: "not_selected" }
    };
    yamlBox.textContent = toYaml(data);
  }

  // ===== ECU INFO =====
  function renderEcuInfo() {
    const ecu = lastAnalysis?.ecu_type || "Desconocida";
    const size = lastAnalysis?.bin_size || (lastFile?.size || 0);

    ecuInfo.innerHTML = `
      <div><strong>ECU Type:</strong> ${ecu}</div>
      <div><strong>Motor:</strong> ${engineDetected}</div>
      <div><strong>File size:</strong> ${size} bytes</div>
    `;
  }

  // ===== Crear orden demo y redirigir a checkout =====
  async function createOrderAndGoCheckout(patchId) {
    if (!lastAnalysis?.analysis_id) {
      alert("Primero analiza el BIN.");
      return;
    }

    try {
      const r = await fetch("/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          analysis_id: lastAnalysis.analysis_id,
          patch_option_id: patchId
        })
      });

      if (!r.ok) {
        const t = await r.text().catch(() => "(sin detalle)");
        alert("No se pudo crear la orden:\n" + t);
        return;
      }

      const order = await r.json();
      // order.id es UUID
      location.href = `/static/checkout.html?order_id=${encodeURIComponent(order.id)}`;
    } catch (e) {
      alert("Error de red creando la orden.");
    }
  }

  // ===== PATCHES (demo) =====
  function renderPatches(ecu) {
    patchList.innerHTML = "";

    if (!ecu || ecu === "UNKNOWN") {
      patchList.innerHTML = `<div class="patch"><div class="title">No hay parches disponibles</div></div>`;
      return;
    }

    // demo: solo 1 parche para EDC17C81
    patchList.innerHTML = `
      <div class="patch">
        <div class="title">DPF OFF — ${ecu} (diesel) — $59</div>
        <button id="btnApplyPatch" class="btn">Aplicar / Comprar</button>
      </div>
    `;

    $("#btnApplyPatch").onclick = async () => {
      // marcar en YAML
      updateYaml({
        status: "selected",
        id: "dpf_off",
        label: "DPF OFF",
        price_usd: 59
      });

      // crear orden + ir a checkout
      await createOrderAndGoCheckout("dpf_off");
    };
  }

  // ===== CRC32 simple =====
  function crc32(buf) {
    let c = 0xffffffff;
    for (let i = 0; i < buf.length; i++) {
      c ^= buf[i];
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    return (c ^ 0xffffffff) >>> 0;
  }

  $("#binfile").addEventListener("change", async (e) => {
    lastFile = e.target.files[0] || null;
    if (!lastFile) return;
    const buf = new Uint8Array(await lastFile.arrayBuffer());
    lastCvn = crc32(buf).toString(16).toUpperCase().padStart(8, "0");
    updateYaml(); // refresca YAML con archivo cargado
  });

  // ===== ANALIZAR BIN =====
  $("#btnAnalizar").onclick = async () => {
    if (!lastFile) return alert("Selecciona un BIN");

    const fd = new FormData();
    fd.append("bin_file", lastFile);

    const r = await fetch("/analyze_bin", { method: "POST", body: fd });
    if (!r.ok) {
      const t = await r.text().catch(() => "(sin detalle)");
      return alert("No se pudo analizar el BIN\n" + t);
    }

    lastAnalysis = await r.json();

    engineDetected = /EDC|DCM|MD1/i.test(lastAnalysis.ecu_type || "")
      ? "diesel"
      : "petrol";

    renderEcuInfo();
    renderPatches(lastAnalysis.ecu_type);
    updateYaml();
  };

  // INIT
  fillBrands();
  updateYaml();
    // ===== LOGIN DEMO =====
  const btnLogin = document.getElementById("btnLogin");
  const btnLogout = document.getElementById("btnLogout");

  if (btnLogin) {
    btnLogin.onclick = () => {
      // te manda a la pantalla de login/listado (ajusta si tu ruta es otra)
      location.href = "/static/usuarios.html?next=/static/index.html";
    };
  }

  if (btnLogout) {
    btnLogout.onclick = () => {
      localStorage.removeItem("EFX_TOKEN");
      alert("Sesión cerrada (demo).");
      location.reload();
    };
  }
})();

