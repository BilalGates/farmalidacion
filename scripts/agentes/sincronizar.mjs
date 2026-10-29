#!/usr/bin/env node
/**
 * Genera la configuracion de agentes y skills de cada herramienta a partir de
 * la fuente unica en `.agents/`:
 *
 *   .agents/agents/<id>/agent.md  ──►  .claude/agents/<id>.md      (Claude Code)
 *                                 ──►  .opencode/agents/<id>.md    (OpenCode)
 *                                 ──►  .codex/agents/<id>.toml     (Codex)
 *                                      (Antigravity lee la fuente directamente)
 *   .agents/skills/<skill>/       ──►  .claude/skills/<skill>/     (Claude Code)
 *                                      (Codex, OpenCode y Antigravity leen .agents/skills)
 *
 *   node scripts/agentes/sincronizar.mjs           # escribe
 *   node scripts/agentes/sincronizar.mjs --check   # falla si algo esta desincronizado
 *
 * Lo generado lleva una cabecera "GENERADO" y no se edita a mano.
 */
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = process.cwd();
const FUENTE_AGENTES = join(ROOT, ".agents/agents");
const FUENTE_SKILLS = join(ROOT, ".agents/skills");
const CHECK = process.argv.includes("--check");

// Nivel neutral → modelo/esfuerzo de cada herramienta. Cambiar aqui y regenerar.
const NIVEL = {
  barato: { claude: "haiku", codexEsfuerzo: "low" },
  medio: { claude: "sonnet", codexEsfuerzo: "medium" },
  fuerte: { claude: "opus", codexEsfuerzo: "high" },
};
const AVISO = "GENERADO por scripts/agentes/sincronizar.mjs desde .agents/agents — no editar a mano.";

// ── Fuente ──────────────────────────────────────────────────────────────────
function leerFrontmatter(texto, ruta) {
  const m = texto.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) throw new Error(`${ruta}: falta la cabecera YAML`);
  const datos = {};
  for (const linea of m[1].split(/\r?\n/)) {
    const kv = linea.match(/^(\w+):\s*(.*)$/);
    if (!kv) continue;
    let valor = kv[2].trim();
    if (valor.startsWith("[")) valor = valor.slice(1, -1).split(",").map((s) => s.trim()).filter(Boolean);
    datos[kv[1]] = valor;
  }
  for (const campo of ["name", "description", "nivel", "capacidades"]) {
    if (!datos[campo]) throw new Error(`${ruta}: falta el campo \`${campo}\``);
  }
  if (!NIVEL[datos.nivel]) throw new Error(`${ruta}: nivel \`${datos.nivel}\` no es barato|medio|fuerte`);
  return { ...datos, cuerpo: m[2].trim() };
}

const agentes = readdirSync(FUENTE_AGENTES)
  .filter((id) => existsSync(join(FUENTE_AGENTES, id, "agent.md")))
  .map((id) => {
    const ruta = join(FUENTE_AGENTES, id, "agent.md");
    // Normaliza CRLF: en Windows la fuente puede guardarse con \r\n y lo generado
    // no debe depender del editor que la toco.
    const a = leerFrontmatter(readFileSync(ruta, "utf8").replace(/\r\n/g, "\n"), relative(ROOT, ruta));
    if (a.name !== id) throw new Error(`${relative(ROOT, ruta)}: name \`${a.name}\` no coincide con la carpeta \`${id}\``);
    return a;
  });

const tiene = (a, c) => a.capacidades.includes(c);
const descripcion = (a) => (a.nombre ? `${a.nombre} — ${a.description}` : a.description);
const yamlTexto = (s) => JSON.stringify(s); // JSON es YAML valido y escapa comillas

// ── Generadores por herramienta ─────────────────────────────────────────────
function claude(a) {
  const tools = ["Read", "Grep", "Glob"];
  if (tiene(a, "editar")) tools.push("Edit", "Write");
  if (tiene(a, "shell")) tools.push("Bash");
  if (tiene(a, "red")) tools.push("WebFetch", "WebSearch");
  if (tiene(a, "delegar")) tools.push("Agent");
  return `---
name: ${a.name}
description: ${yamlTexto(descripcion(a))}
tools: ${tools.join(", ")}
model: ${NIVEL[a.nivel].claude}
---

<!-- ${AVISO} -->

${a.cuerpo}
`;
}

function opencode(a) {
  // Sintaxis \`permission\` heredada: la V2 (\`permissions\`) se parsea pero no se aplica (opencode#50598).
  const permitir = (c) => (tiene(a, c) ? "allow" : "deny");
  return `---
description: ${yamlTexto(descripcion(a))}
mode: ${a.name === "pep" ? "all" : "subagent"}
permission:
  edit: ${permitir("editar")}
  bash: ${tiene(a, "shell") ? "allow" : "deny"}
  webfetch: ${permitir("red")}
---

<!-- ${AVISO} -->

${a.cuerpo}
`;
}

function codex(a) {
  const sandbox = tiene(a, "editar") ? "workspace-write" : "read-only";
  // Cadena literal multilinea TOML: no puede contener ''' (se comprueba).
  if (a.cuerpo.includes("'''")) throw new Error(`${a.name}: el cuerpo contiene ''' y rompe el TOML`);
  return `# ${AVISO}
name = ${JSON.stringify(a.name)}
description = ${JSON.stringify(descripcion(a))}
model_reasoning_effort = "${NIVEL[a.nivel].codexEsfuerzo}"
sandbox_mode = "${sandbox}"
developer_instructions = '''
${a.cuerpo}
'''
`;
}

// ── Escritura / comprobacion ────────────────────────────────────────────────
const desfases = [];

function volcar(dir, ext, generar) {
  const esperados = new Map(agentes.map((a) => [`${a.name}.${ext}`, generar(a)]));
  if (!CHECK) mkdirSync(dir, { recursive: true });
  for (const [nombre, contenido] of esperados) {
    const ruta = join(dir, nombre);
    const actual = existsSync(ruta) ? readFileSync(ruta, "utf8").replace(/\r\n/g, "\n") : null;
    if (actual === contenido) continue;
    if (CHECK) desfases.push(relative(ROOT, ruta));
    else writeFileSync(ruta, contenido);
  }
  // Lo que sobra en el destino y no viene de la fuente (agentes retirados).
  if (!existsSync(dir)) return;
  for (const nombre of readdirSync(dir)) {
    if (!nombre.endsWith(`.${ext}`) || esperados.has(nombre)) continue;
    if (CHECK) desfases.push(`${relative(ROOT, join(dir, nombre))} (sobra)`);
    else rmSync(join(dir, nombre));
  }
}

function listarArbol(dir, base = dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((n) => {
    if (n === "__pycache__") return [];
    const r = join(dir, n);
    return statSync(r).isDirectory() ? listarArbol(r, base) : [relative(base, r)];
  });
}

function espejoSkills(destino) {
  const fuente = new Set(listarArbol(FUENTE_SKILLS));
  const dest = new Set(listarArbol(destino));
  const iguales = (f) => readFileSync(join(FUENTE_SKILLS, f)).equals(readFileSync(join(destino, f)));
  const distintos = [...fuente].filter((f) => !dest.has(f) || !iguales(f));
  const sobran = [...dest].filter((f) => !fuente.has(f));
  if (CHECK) {
    desfases.push(...distintos.map((f) => relative(ROOT, join(destino, f))));
    desfases.push(...sobran.map((f) => `${relative(ROOT, join(destino, f))} (sobra)`));
    return;
  }
  if (distintos.length || sobran.length) {
    rmSync(destino, { recursive: true, force: true });
    cpSync(FUENTE_SKILLS, destino, { recursive: true, filter: (s) => !s.includes("__pycache__") });
  }
}

volcar(join(ROOT, ".claude/agents"), "md", claude);
volcar(join(ROOT, ".opencode/agents"), "md", opencode);
volcar(join(ROOT, ".codex/agents"), "toml", codex);
espejoSkills(join(ROOT, ".claude/skills"));

if (CHECK) {
  if (desfases.length) {
    console.error(`Agentes desincronizados (${desfases.length}). Ejecuta \`node scripts/agentes/sincronizar.mjs\`:`);
    for (const d of desfases) console.error(`  - ${d}`);
    process.exit(1);
  }
  console.log(`ok agentes sincronizados (${agentes.length} agentes).`);
} else {
  console.log(`Sincronizados ${agentes.length} agentes: ${agentes.map((a) => a.nombre ?? a.name).join(", ")}.`);
}
