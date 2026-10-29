#!/usr/bin/env node
/**
 * Instala el kit de agentes en el proyecto actual (ejecutar desde su raiz):
 *
 *   node scripts/agentes/instalar.mjs
 *
 * 1. Activa los git hooks del kit (`core.hooksPath .githooks`).
 * 2. Crea CLAUDE.md apuntando a AGENTS.md si no existe; si existe, avisa.
 * 3. Genera los agentes de Claude Code, Codex y OpenCode (sincronizar.mjs).
 * 4. Recuerda el siguiente paso: la induccion de Pep.
 *
 * No borra nada del proyecto.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";

const git = (...a) => {
  try {
    return execFileSync("git", a, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
};

if (git("rev-parse", "--is-inside-work-tree") === "true") {
  git("config", "core.hooksPath", ".githooks");
  console.log("ok  git hooks activados (.githooks)");
} else {
  console.log("--  no es un repositorio git: hooks sin activar");
}

const IMPORT = "@AGENTS.md\n@.agents/proyecto.md\n";
if (!existsSync("CLAUDE.md")) {
  writeFileSync("CLAUDE.md", `# CLAUDE.md\n\nLa fuente principal es AGENTS.md, comun a Claude Code, Codex, OpenCode y Antigravity.\n\n${IMPORT}`);
  console.log("ok  CLAUDE.md creado (apunta a AGENTS.md)");
} else if (!readFileSync("CLAUDE.md", "utf8").includes("@AGENTS.md")) {
  console.log("!!  Ya existe CLAUDE.md: pasa sus reglas a .agents/proyecto.md durante la induccion y dejalo en:\n" + IMPORT);
}

execFileSync("node", ["scripts/agentes/sincronizar.mjs"], { stdio: "inherit" });

console.log(`
Siguiente paso: abre el proyecto con tu herramienta (Claude Code, Codex, OpenCode
o Antigravity) y pide: "Pep, haz la induccion del proyecto".
Pep creara .agents/proyecto.md y te propondra las skills del proyecto.`);
