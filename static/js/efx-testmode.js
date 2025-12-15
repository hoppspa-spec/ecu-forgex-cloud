(function(){
  const _origLoad = window.loadPatchesCombined;
  const _origFill = window.fillPatches;

  window.loadPatchesCombined = async function(engineMode, ecuFamily, brandKey){
    const out = await _origLoad.call(this, engineMode, ecuFamily, brandKey);
    if(!window.__TEST_MODE__) return out;
    const must = (window.__TEST_FAMILY__||"").toUpperCase();
    const patches = (out.patches||[]).filter(p => (p.compatible_ecu||[]).some(f => String(f).toUpperCase().includes(must)));
    return { patches, packs: out.packs||[] };
  };

  window.fillPatches = async function(){
    await _origFill.call(this);
    if(!window.__TEST_MODE__) return;
    const fam = (window.lastAnalysis?.ecu_type||"").toUpperCase();
    const must = (window.__TEST_FAMILY__||"").toUpperCase();
    if(fam && !fam.includes(must)){
      const msg = document.getElementById("noPatchMsg");
      if(msg){ msg.style.display="block"; msg.textContent="Modo prueba activo: solo "+window.__TEST_FAMILY__; }
    }
  };
})();
