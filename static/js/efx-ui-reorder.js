document.addEventListener("DOMContentLoaded", ()=>{
  const cols = document.querySelectorAll(".container > .card");
  if(cols.length !== 3) return;
  const [left, center, right] = cols;
  const mustReorder = !/Información del Vehículo/i.test(left.textContent||"");
  if(!mustReorder) return;

  const container = document.querySelector(".container");
  const cardVeh  = [...cols].find(c => /Información del Vehículo/i.test(c.textContent||"")) || left;
  const cardYml  = [...cols].find(c => /Resumen YAML/i.test(c.textContent||"")) || right;
  const cardParc = [...cols].find(c => /Parches Disponibles/i.test(c.textContent||"")) || center;

  container.innerHTML = "";
  container.append(cardVeh);
  container.append(cardParc);
  container.append(cardYml);
});
