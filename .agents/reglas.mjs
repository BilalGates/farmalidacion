// Reglas comprobables de Farmalidación. El pre-commit del kit pasa cada fichero
// preparado y muestra los avisos; nunca bloquea. Contrato:
//   export default (ruta, texto) => string[]
import { execFileSync } from "node:child_process";

const FRONT = "validador-fichas-tecnicas-repo-kit/frontend/src/";
const HOJAS_NUEVAS = /frontend\/src\/(ui|screens)\/[^/]+\.css$/;
const HISTORICAS = /frontend\/src\/(styles|studio)\.css$/;
// Formas de usted que ya se retiraron de la interfaz (la app trata de tú).
const USTED = /['">`]\s*(Seleccione|Consulte|Revise|Pruebe|Indique|Inténtelo|Recargue|Filtre|Añada|Elija|Abra|Pulse|Introduzca|Escriba|Identifíquese|Compruebe|Revíse\p{L}*)(?!\p{L})/u;
// Caracteres que se usaron como iconos; los iconos vienen de lucide-react.
const ICONOS_TEXTO = /[◷✓⌕▤↻◇]/;

function lineasHead(ruta) {
  try {
    return execFileSync("git", ["show", `HEAD:${ruta}`], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).split("\n").length;
  } catch {
    return null;
  }
}

export default function revisar(ruta, texto) {
  const avisos = [];
  const r = ruta.replace(/\\/g, "/");

  if (HOJAS_NUEVAS.test(r) && !r.endsWith("/tokens.css")) {
    const css = texto.replace(/\/\*[\s\S]*?\*\//g, "");
    if (/#[0-9a-f]{3,8}\b/i.test(css) || /\brgba?\(/.test(css)) avisos.push("color escrito a mano: usa un token de ui/tokens.css");
    if (/font-size:\s*[0-9.]+(rem|px|em)/.test(css)) avisos.push("tamaño de letra escrito a mano: usa --text-*");
  }

  if (HISTORICAS.test(r)) {
    const antes = lineasHead(r);
    const ahora = texto.split("\n").length;
    if (antes !== null && ahora > antes) avisos.push(`hoja histórica que crece (${antes} → ${ahora} líneas): lo nuevo va en ui/ o screens/`);
  }

  if (r.startsWith(FRONT) && /\.tsx$/.test(r) && !/\.test\.tsx$/.test(r)) {
    texto.split("\n").forEach((linea, i) => {
      if (USTED.test(linea)) avisos.push(`l.${i + 1}: texto tratando de usted; la interfaz trata de tú`);
      if (ICONOS_TEXTO.test(linea)) avisos.push(`l.${i + 1}: carácter usado como icono; usa lucide-react`);
    });
  }

  return avisos;
}
