// git pre-commit del kit. Si el proyecto define `.agents/reglas.mjs` (lo crea
// Pep en la induccion cuando hay reglas comprobables), se le pasa cada fichero
// preparado. Contrato: `export default (ruta, texto) => string[]` de avisos.
// Avisa, nunca bloquea.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const reglas = resolve(".agents/reglas.mjs");
if (!existsSync(reglas)) process.exit(0);

try {
  const revisar = (await import(pathToFileURL(reglas).href)).default;
  const preparados = execFileSync("git", ["diff", "--cached", "--name-only", "--diff-filter=AM"], { encoding: "utf8" })
    .split("\n")
    .filter(Boolean);
  const avisos = [];
  for (const ruta of preparados) {
    let texto = "";
    try {
      texto = readFileSync(ruta, "utf8");
    } catch {
      continue;
    }
    const hallazgos = revisar(ruta, texto) || [];
    if (hallazgos.length) avisos.push(`${ruta}:\n${hallazgos.map((h) => `  ${h}`).join("\n")}`);
  }
  if (avisos.length) process.stderr.write(`\n[agentes] Reglas del proyecto:\n${avisos.join("\n")}\nAviso, no bloquea.\n\n`);
} catch {
  // Un hook nunca falla.
}
process.exit(0);
