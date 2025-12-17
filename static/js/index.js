// static/js/index.js
(() => {
  // ====== AUTH (simple) ======
  // El login real debe guardar EFX_TOKEN en localStorage.
  // Si no tienes login aún, igual funciona: te redirige a usuarios.html
  const ADMIN_EMAIL = "demo@ecuforge.dev";
  let TOKEN = localStorage.getItem("EFX_TOKEN") || null;

  let lastFile = null;
  let lastCvn = null;
  let lastAnalysis = null;
  let engineDetected = "auto";

  const $ = (q) => document.querySelector(q);
  const yamlBox = $("#yamlBox");
  const ecuInfo = $("#ecuInfo");
  const patchList = $("#patchList");

  const btnLogin = $("#btnLogin");
  const btnLogout = $("#btnLogout");

  function setAuthUi() {
    if (!btnLogin || !btnLogout) return;
    btnLogin.style.display = TOKEN ? "none" : "inline-block";
    btnLogout.style.display = TOKEN ? "inline-block" : "none";
  }

  btnLogin?.addEventListener("click", () => {
    // manda a login (con retorno)
    location.href = "/static/usuarios.html?next=/static/index.html";
  });

  btnLogout?.addEventListener("click", () => {
    TOKEN = null;
    localStorage.removeItem("EFX_TOKEN");
    setAuthUi();
    location.reload();
  });

  async function ensureAuthOrRedirect() {
    if (TOKEN) return true;
    location.href = "/static/usuarios.html?next=/static/index.html";
    return false;
  }

  // ====== VEHÍCULOS (demo funcional) ======
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
    const selYear = $("#selYear");

    selBrand.innerHTML = `<option value="">— Selecciona —</option>`;
    VEH.brands.forEach((b) => selBrand.append(new Option(b.label, b.key)));

    selBrand.onchange = () => {
      const brand = VEH.brands.find((b) => b.key === selBrand.value);
      selModel.innerHTML = `<option value="">— Selecciona —</option>`;
      selYear.innerHTML = `<option value="">— Selecciona —</option>`;
      if (!brand) return;

      brand.models.forEach((m) => selModel.append(new Option(m.label, m.key)));
    };

    selModel.onchange = () => {
      const brand = VEH.brands.find((b) => b.key === selBrand.value);
      const model = brand?.models.find((m) => m.key === selModel.value);
      selYear.innerHTML = `<option value="">— Selecciona —</option>`;
      model?.years.forEach((y) => selYear.append(new Option(y, y)));
    };
  }

  // ====== YAML ======
  function toYaml(obj, indent = 0) {
    const pad = "  ".repeat(indent);
    if (obj === null) return "null";
    if (Array.isArray(obj)) {
      if (!obj.length) return "[]";
      return obj.map((x) => `${pad}- ${typeof x === "object" ? "\n" + toYaml(x, indent + 1) : String(x)}`).join("\n");
    }
    if (typeof obj !== "object") return String(obj);

    let out = [];
    for (const k of Object.keys(obj)) {
      const v = obj[k];
      if (typeof v === "object" && v !== null) {
        out.push(`${pad}${k}:`);
        out.push(toYaml(v, indent + 1));
      } else {
        out.push(`${pad}${k}: ${v === undefined ? "null" : v}`);
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
        name: lastFile?.name || lastAnalysis?.filename || null,
        size_bytes: lastFile?.size || lastAnalysis?.bin_size || null,
        cvn_crc32: lastCvn || lastAnalysis?.cvn_crc32 || null,
      },
      patch: patch || { status: "not_selected" },
    };
    if (yamlBox) yamlBox.textContent = toYaml(data);
  }

  // ====== ECU INFO ======
  function renderEcuInfo() {
    if (!ecuInfo || !lastAnalysis) return;
    ecuInfo.innerHTML = `
      <div><strong>ECU Type:</strong> ${lastAnalysis.ecu_type || "Desconocida"}</div>
      <div><strong>Motor:</strong> ${engineDetected}</div>
      <div><strong>File size:</strong> ${lastAnalysis.bin_size || 0} bytes</div>
    `;
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
    updateYaml(); // actualiza YAML aunque no haya análisis aún
  });

  // ====== PATCHES + COMPRA ======
  async function createOrderAndGoCheckout(patchId) {
    // obliga login
    if (!(await ensureAuthOrRedirect())) return;

    if (!lastAnalysis?.analysis_id) {
      alert("Primero analiza el BIN.");
      return;
    }

    // intenta crear orden
    let r;
    try {
      r = await fetch("/orders", {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + TOKEN,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          analysis_id: lastAnalysis.analysis_id,
          patch_option_id: patchId,
        }),
      });
    } catch (e) {
      alert("Error de red creando orden (/orders).");
      return;
    }

    if (!r.ok) {
      const t = await r.text().catch(() => "(sin detalle)");
      alert(
        "No pude crear la orden.\n" +
          "HTTP " +
          r.status +
          "\n" +
          t +
          "\n\n" +
          "👉 Esto significa que aún no existe /orders en tu backend (o requiere auth distinta)."
      );
      return;
    }

    const d = await r.json();
    if (d.checkout_url) {
      location.href = d.checkout_url;
      return;
    }
    location.href = `/static/checkout.html?order_id=${encodeURIComponent(d.id || "")}`;
  }

  function renderPatchesFromList(items) {
    if (!patchList) return;

    if (!items || !items.length) {
      patchList.innerHTML = `<div class="patch"><div class="title">No hay parches disponibles</div></div>`;
      return;
    }

    patchList.innerHTML = "";
    items.forEach((p) => {
      const price = typeof p.price === "number" ? ` — $${p.price}` : "";
      const el = document.createElement("div");
      el.className = "patch";
      el.innerHTML = `
        <div class="title">${p.label}${price}</div>
        <div class="kv"><div><small class="muted">ID:</small> ${p.id}</div></div>
        <button class="btn" style="margin-top:6px">Aplicar / Comprar</button>
      `;

      el.querySelector("button").onclick = async () => {
        updateYaml({
          status: "selected",
          id: p.id,
          label: p.label,
          price_usd: p.price ?? null,
        });
        await createOrderAndGoCheckout(p.id);
      };

      patchList.appendChild(el);
    });
  }

  async function loadPatchesForEcu(ecuType) {
    if (!patchList) return;

    // 1) intenta backend real: /public/recipes/<ECU>?engine=
    patchList.innerHTML = `<div class="patch"><div class="title">Cargando parches...</div></div>`;
    try {
      const url = `/public/recipes/${encodeURIComponent(ecuType)}?engine=${encodeURIComponent(engineDetected)}`;
      const r = await fetch(url, { cache: "no-store" });
      if (r.ok) {
        const d = await r.json();
        if (d?.recipes?.length) {
          renderPatchesFromList(d.recipes);
          return;
        }
      }
    } catch {}

    // 2) fallback demo (si no hay backend de recetas)
    renderPatchesFromList([
      { id: "dpf_off", label: `DPF OFF — ${ecuType} (${engineDetected})`, price: 59 },
    ]);
  }

  // ====== ANALIZAR BIN ======
  $("#btnAnalizar")?.addEventListener("click", async () => {
    if (!lastFile) return alert("Selecciona un BIN");

    const fd = new FormData();
    fd.append("bin_file", lastFile);

    let r;
    try {
      r = await fetch("/analyze_bin", { method: "POST", body: fd });
    } catch (e) {
      alert("Error de red en /analyze_bin");
      return;
    }

    if (!r.ok) {
      const t = await r.text().catch(() => "(sin detalle)");
      alert("No se pudo analizar el BIN\nHTTP " + r.status + "\n" + t);
      return;
    }

    lastAnalysis = await r.json();

    engineDetected = /EDC|DCM|MD1|MJD|SID/i.test(lastAnalysis.ecu_type || "")
      ? "diesel"
      : /MED|MEVD|MG1|ME7/i.test(lastAnalysis.ecu_type || "")
      ? "petrol"
      : "auto";

    renderEcuInfo();
    updateYaml({ status: "not_selected" });

    const ecu = lastAnalysis.ecu_type || "UNKNOWN";
    await loadPatchesForEcu(ecu);
  });

  // ====== COPY YAML ======
  $("#btnCopyYaml")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(yamlBox?.textContent || "");
      alert("YAML copiado");
    } catch {
      alert("No se pudo copiar");
    }
  });

  // ====== INIT ======
  setAuthUi();
  fillBrands();
  updateYaml();
})();
