// git commit-msg del kit, adaptado a Farmalidación: asunto en castellano que
// empieza por un verbo en infinitivo, sin prefijo de tipo. Avisa, nunca bloquea.
import { readFileSync } from "node:fs";

let mensaje = "";
try {
  mensaje = readFileSync(process.argv[2], "utf8");
} catch {
  process.exit(0);
}

const asunto = mensaje.split("\n").find((l) => l.trim() && !l.startsWith("#")) || "";
const avisos = [];
if (!/^(Merge|Revert) /.test(asunto)) {
  if (/^(feat|fix|refactor|perf|docs|chore|test|build|ci|style)(\([\w./-]+\))?!?: /.test(asunto)) {
    avisos.push(`asunto con prefijo de tipo: "${asunto}" → en este proyecto, sin prefijo: «Corregir …», «Añadir …»`);
  } else if (!/^\p{Lu}\p{Ll}+(ar|er|ir)\b/u.test(asunto)) {
    avisos.push(`el asunto no empieza por un verbo en infinitivo: "${asunto}" → «Corregir …», «Aplicar …»`);
  }
  if (/^(wip|cambios varios|actualizar archivos)\b/i.test(asunto)) avisos.push(`asunto sin contenido: "${asunto}"`);
  if (/\.$/.test(asunto)) avisos.push("el asunto no lleva punto final");
}
if (asunto.length > 72) avisos.push(`asunto de ${asunto.length} caracteres (maximo 72)`);

if (avisos.length) process.stderr.write(`\n[agentes] Mensaje de commit:\n  ${avisos.join("\n  ")}\nAviso, no bloquea.\n\n`);
process.exit(0);
