(function(){
  function renderPanel(){
    const rightCard = [...document.querySelectorAll(".container > .card")]
      .find(c => /Resumen YAML/i.test(c.textContent||""));
    if(!rightCard) return;

    const wrap = document.createElement("div");
    wrap.className = "admin-only";
    wrap.style.display = (document.documentElement.dataset.owner==="1") ? "" : "none";
    wrap.innerHTML = `
      <div class="divider"></div>
      <h3>Offsets (admin)</h3>
      <div style="display:grid;grid-template-columns:120px 1fr 140px;gap:8px;align-items:center">
        <label class="muted">SW number</label>
        <input id="off_sw" placeholder="10SW05263416"/>
        <input id="off_sw_ofs" placeholder="0x0010001A"/>
        <label class="muted">MPC tipo</label>
        <input id="off_mpc" placeholder="BASE_ECU tc1782"/>
        <input id="off_mpc_ofs" placeholder="0x001000FD"/>
        <label class="muted">ECU type</label>
        <input id="off_ecu" placeholder="BOSCH EDC17C81"/>
        <input id="off_ecu_ofs" placeholder="0x001000EE"/>
      </div>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button id="btnOffsetsSave" class="btn sm">Guardar</button>
        <button id="btnOffsetsFill" class="btn sm" style="background:#334155">Autocompletar</button>
      </div>
      <pre id="off_dbg" class="yaml-box" style="max-height:120px;margin-top:8px"></pre>
    `;
    rightCard.append(wrap);

    const KEY="EFX_OFFSETS_EDC17C81";
    function save(){
      const data = {
        sw:   off_sw.value.trim(),
        swOf: off_sw_ofs.value.trim(),
        mpc:  off_mpc.value.trim(),
        mpcOf:off_mpc_ofs.value.trim(),
        ecu:  off_ecu.value.trim(),
        ecuOf:off_ecu_ofs.value.trim()
      };
      localStorage.setItem(KEY, JSON.stringify(data));
      showDbg(data);
    }
    function load(){
      try{
        const d = JSON.parse(localStorage.getItem(KEY)||"{}");
        Object.entries(d).forEach(([k,v])=>{ const e=document.getElementById("off_"+k); if(e) e.value=v; });
        showDbg(d);
      }catch{}
    }
    function showDbg(d){
      off_dbg.textContent = [
        "EDC17C81 Offsets:",
        `SW:  ${d.sw||"-"} @ ${d.swOf||"-"}`,
        `MPC: ${d.mpc||"-"} @ ${d.mpcOf||"-"}`,
        `ECU: ${d.ecu||"-"} @ ${d.ecuOf||"-"}`
      ].join("\n");
    }
    btnOffsetsSave.onclick = save;
    btnOffsetsFill.onclick = ()=>{
      const ecu = window.lastAnalysis?.ecu_type || "";
      if(ecu) off_ecu.value = ecu;
      save();
    };
    load();
  }
  document.addEventListener("DOMContentLoaded", renderPanel);
})();
