// static/js/index.js
(() => {
  // ========= CONFIG =========
  const ADMIN_EMAIL = "demo@ecuforge.dev"; // cámbialo por tu mail real
  const API = {
    me: "/users/me",
    analyze: "/public/analyze_bin",
    recipes: (family, engine) =>
      `/public/recipes/${encodeURIComponent(family)}?engine=${encodeURIComponent(engine || "auto")}`,
    globalPatches: "/static/patches/global.json",
    orders: "/orders",
    loginUrl: "/static/usuarios.html?next=/static/index.html",
  };

  // ========= STATE =========
  let TOKEN = localStorage.getItem("EFX_TOKEN") || null;
  let CURRENT_USER = null;

  let lastFile = null;
  let lastCvn = null;
  let lastAnalysis = null;
  let engineDetected = "auto";

  // ========= DOM =========
  const $ = (q, el = document) => el.querySelector(q);

  const selBrand = $("#selBrand");
  const selModel = $("#selModel");
  const selYear = $("#selYear");

  const inputFile = $("#binfile");
  const btnAnalizar = $("#btnAnalizar");
  const btnCopyYaml = $("#btnCopyYaml");

  const ecuInfo = $("#ecuInfo");
  const yamlBox = $("#yamlBox");

  const patchList =
    document.getElementById("patchList") ||
    document.getElementById("patches-list");

  const debugBox = $("#debugBox");
  const debugContent = $("#debugContent");

  const btnLogin = $("#btnLogin");
  const btnLogout = $("#btnLogout");

  // ========= DATA (demo mínimo) =========
  const VEH = {
    brands: [
      {
        key: "maxus",
        label: "Maxus",
        models: [
          { key: "t60", label: "T60 (LDV T60)", years: ["2017-2022"] },
        ],
      },
    ],
  };

  // ========= HELPERS =========
  function setAuthUi(isAuthed) {
    if (btnLogin) btnLogin.style.display = isAuthed ? "none" : "inline-block";
    if (btnLogout)
      btnLogout.style.display = isAuthed ? "inline-block" : "none";
  }

  async function fetchMe() {
    if (!TOKEN) return null;
    try {
      const r = await fetch(API.me, {
        headers: { Authorization: "Bearer " + TOKEN },
        cache: "no-store",
      });
      if (!r.ok) return null;
      return await r.json();
    } catch {
      return null;
    }
  }

  function toYaml(obj, indent = 0) {
    const pad = "  ".repeat(indent);

    if (obj === null || obj === undefined) return "null";

    if (Array.isArray(obj)) {
      if (!obj.length) return "[]";
      return obj
        .map((x) => {
          if (typeof x === "object" && x !== null) {
            return `${pad}-\n${toYaml(x, indent + 1)}`;
          }
          return `${pad}- ${String(x)}`;
        })
        .join("\n");
    }

    if (typeof obj === "object") {
      const lines = [];
      for (const k of Object.keys(obj)) {
        const v = obj[k];
        if (typeof v === "object" && v !== null && !Array.isArray(v)) {
          lines.push(`${pad}${k}:`);
          lines.push(toYaml(v, indent + 1));
        } else if (Array.isArray(v)) {
          lines.push(`${pad}${k}:`);
          lines.push(toYaml(v, indent + 1));
        } else {
          lines.push(
            `${pad}${k}: ${v === null || v === undefined || v === "" ? "null" : String(v)}`
          );
        }
      }
      return lines.join("\n");
    }

    return String(obj);
  }

  function updateYaml({ patch }) {
    const obj = {
      ecu: {
        type: lastAnalysis?.ecu_type || null,
        part_number: lastAnalysis?.ecu_part_number || null,
      },
      file: {
        name: lastAnalysis?.filename || lastFile?.name || null,
        size_bytes: lastAnalysis?.bin_size || lastFile?.size || null,
        cvn_crc32: lastCvn || null,
      },
      patch: patch || { status: "not_selected" },
    };
    if (yamlBox) yamlBox.textContent = toYaml(obj);
  }

  function setEcuInfoHtml() {
    if (!ecuInfo) return;

    const ecu = lastAnalysis?.ecu_type || "Desconocida";
    const pn = lastAnalysis?.ecu_part_number || "—";
    const size = new Intl.NumberFormat("es-CL").format(
      lastAnalysis?.bin_size || 0
    );
    const motor = engineDetected;

    ecuInfo.innerHTML = `
      <div><strong>ECU Type:</strong> ${ecu}</div>
      <div><strong>Part Number:</strong> ${pn}</div>
      <div><strong>File size:</strong> ${size} bytes</div>
      <div><strong>Motor:</strong> ${motor}</div>
    `;
  }

  // ========= CRC32 (estable) =========
  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(u8) {
    let c = 0 ^ -1;
    for (let i = 0; i < u8.length; i++) {
      c = (c >>> 8) ^ CRC_TABLE[(c ^ u8[i]) & 0xff];
    }
    return (c ^ -1) >>> 0;
  }

  // ========= DROPDOWNS =========
  function fillBrands() {
    if (!selBrand || !selModel || !selYear) return;

    selBrand.innerHTML = `<option value="">— Selecciona —</option>`;
    VEH.brands.forEach((b) => selBrand.appendChild(new Option(b.label, b.key)));

    selModel.innerHTML = `<option value="">— Selecciona —</option>`;
    selYear.innerHTML = `<option value="">— Selecciona —</option>`;
    selModel.disabled = true;
    selYear.disabled = true;

    selBrand.onchange = () => {
      const b = VEH.brands.find((x) => x.key === selBrand.value);
      selModel.innerHTML = `<option value="">— Selecciona —</option>`;
      selYear.innerHTML = `<option value="">— Selecciona —</option>`;
      selYear.disabled = true;

      if (!b) {
        selModel.disabled = true;
        return;
      }

      (b.models || []).forEach((m) =>
        selModel.appendChild(new Option(m.label, m.key))
      );
      selModel.disabled = false;
    };

    selModel.onchange = () => {
      const b = VEH.brands.find((x) => x.key === selBrand.value);
      const m = (b?.models || []).find((x) => x.key === selModel.value);

      selYear.innerHTML = `<option value="">— Selecciona —</option>`;
      if (!m) {
        selYear.disabled = true;
        return;
      }

      (m.years || []).forEach((y) => selYear.appendChild(new Option(y, y)));
      selYear.disabled = false;
    };
  }

  // ========= AUTH / ORDER =========
  btnLogin?.addEventListener("click", () => {
    alert("Modo demo: usa tu login real (si está implementado).");
  });

  btnLogout?.addEventListener("click", () => {
    TOKEN = null;
    localStorage.removeItem("EFX_TOKEN");
    setAuthUi(false);
    location.reload();
  });

  async function ensureAuth() {
    if (!TOKEN) {
      alert("Debes iniciar sesión para comprar.");
      location.href = API.loginUrl;
      return false;
    }
    try {
      const r = await fetch(API.me, {
        headers: { Authorization: "Bearer " + TOKEN },
        cache: "no-store",
      });
      if (r.ok) return true;
    } catch {}
    alert("Sesión inválida. Inicia sesión de nuevo.");
    location.href = API.loginUrl;
    return false;
  }

  async function createOrder(patch) {
    if (!(await ensureAuth())) return;
    if (!lastAnalysis?.analysis_id) {
      alert("Analiza un BIN primero.");
      return;
    }

    try {
      const r = await fetch(API.orders, {
        method: "POST",
        headers: {
          Authorization: "Bearer " + TOKEN,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          analysis_id: lastAnalysis.analysis_id,
          patch_option_id: patch.id,
        }),
      });

      if (!r.ok) {
        const t = await r.text().catch(() => "(sin detalle)");
        alert("Error creando la orden:\n" + t);
        return;
      }

      const d = await r.json();
      location.href =
        d.checkout_url || `/static/checkout.html?order_id=${encodeURIComponent(d.id)}`;
    } catch {
      alert("Error de red creando orden.");
    }
  }

  // ========= PATCHES =========
  function renderPatches(items) {
    if (!patchList) return;

    if (!items || !items.length) {
      patchList.innerHTML = `
        <div class="patch"><div class="title">No hay parches disponibles</div></div>
      `;
      return;
    }

    patchList.innerHTML = "";
    items.forEach((p) => {
      const price =
        typeof p.price === "number"
          ? ` — $${p.price}`
          : p.price?.USD != null
          ? ` — $${p.price.USD}`
          : "";

      const el = document.createElement("div");
      el.className = "patch";
      el.innerHTML = `
        <div class="title">${p.label}${price}</div>
        <div class="kv"><small>ID:</small> ${p.id}</div>
        <button class="btn" style="margin-top:6px">Aplicar / Comprar</button>
      `;

      el.querySelector("button").onclick = async () => {
        updateYaml({
          patch: {
            status: "selected",
            id: p.id,
            label: p.label,
            price_usd: p.price?.USD ?? p.price ?? null,
          },
        });
        await createOrder(p); // si /orders existe, pasa a checkout
      };

      patchList.appendChild(el);
    });
  }

  async function loadFamilyPatches(family, engine) {
    if (patchList) {
      patchList.innerHTML = `<div class="patch"><div class="title">Cargando parches...</div></div>`;
    }

    // 1) Backend (carpeta-recipes)
    try {
      const r = await fetch(API.recipes(family, engine), { cache: "no-store" });
      if (r.ok) {
        const d = await r.json();
        if (d?.recipes?.length) {
          renderPatches(d.recipes);
          return;
        }
      }
    } catch {}

    // 2) Fallback global.json
    try {
      const g = await fetch(API.globalPatches, { cache: "no-store" });
      if (g.ok) {
        const data = await g.json();
        const patches = (data.patches || []).filter((p) =>
          (p.compatible_ecu || []).some(
            (e) => String(e).toUpperCase() === String(family).toUpperCase()
          )
        );
        renderPatches(patches);
        return;
      }
    } catch {}

    renderPatches([]);
  }

  // ========= FILE HANDLING =========
  inputFile?.addEventListener("change", async (e) => {
    lastFile = e.target.files?.[0] || null;
    lastAnalysis = null;
    engineDetected = "auto";
    lastCvn = null;

    if (!lastFile) return;

    const buf = new Uint8Array(await lastFile.arrayBuffer());
    lastCvn = crc32(buf).toString(16).toUpperCase().padStart(8, "0");

    // limpia UI suave
    if (ecuInfo) ecuInfo.innerHTML = `Esperando análisis...`;
    updateYaml({ patch: { status: "not_selected" } });
    renderPatches([]);
  });

  btnAnalizar?.addEventListener("click", async () => {
    const f = inputFile?.files?.[0];
    if (!f) return alert("Selecciona un BIN");
    if (!/\.(bin|mpc|org|e2p|101)$/i.test(f.name || "")) {
      return alert("Formato no soportado.");
    }

    const fd = new FormData();
    fd.append("bin_file", f);

    let r;
    try {
      r = await fetch(API.analyze, { method: "POST", body: fd });
    } catch {
      alert("Error de red en análisis.");
      return;
    }

    if (!r.ok) {
      const t = await r.text().catch(() => "(sin detalle)");
      alert("No se pudo analizar el BIN. HTTP " + r.status + "\n" + t);
      return;
    }

    const data = await r.json();
    lastAnalysis = data;

    // Motor heurístico
    if (/EDC|MD1|MJD|DCM|SID/i.test(data.ecu_type || "")) engineDetected = "diesel";
    else if (/MED|MG1|MEVD|ME7/i.test(data.ecu_type || "")) engineDetected = "petrol";
    else engineDetected = "auto";

    setEcuInfoHtml();
    updateYaml({ patch: { status: "not_selected" } });

    // carga parches por familia detectada
    const family = data.ecu_type || "EDC17C81";
    await loadFamilyPatches(family, engineDetected);
  });

  // ========= COPY YAML =========
  btnCopyYaml?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(yamlBox?.textContent || "");
      alert("YAML copiado.");
    } catch {
      alert("No se pudo copiar.");
    }
  });

  // ========= INIT =========
  (async function init() {
    fillBrands(); // <-- ESTO era lo que te faltaba para los dropdowns

    setAuthUi(!!TOKEN);
    CURRENT_USER = await fetchMe();

    const userEmail = (
      CURRENT_USER?.email ||
      CURRENT_USER?.username ||
      ""
    ).toLowerCase();

    const isAdmin = !!userEmail && userEmail === ADMIN_EMAIL.toLowerCase();
    if (isAdmin && debugBox) {
      debugBox.style.display = "block";
      if (debugContent) debugContent.innerHTML = `<small class="muted">Debug activo</small>`;
    }
  })();
})();
