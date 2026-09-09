// Ejecuta el bloque CONSEJO-CORE extraído de docs/index.html con casos de
// prueba. Lee JSON por stdin y escribe JSON por stdout:
//   entrada: { core: "<bloque JS>", cases: [{name, body}],
//              seq: [{from, date, body}] }
//   salida:  { cases: {name: {candId: voto}}, seq: {porAutor, tally} }
//
// El bloque es JS puro (sin DOM ni red) precisamente para poder testearlo
// aquí: mismo patrón que la Mesa del Puente (city/parcels/arena/tests/).
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const Consejo = new Function(input.core + "\nreturn Consejo;")();

const out = { cases: {}, seq: null };
for (const c of input.cases || []) out.cases[c.name] = Consejo.parsePapeleta(c.body);
if (input.seq) {
  const porAutor = Consejo.escrutar(input.seq);
  out.seq = { porAutor: porAutor, tally: Consejo.tally(porAutor) };
}
process.stdout.write(JSON.stringify(out));
