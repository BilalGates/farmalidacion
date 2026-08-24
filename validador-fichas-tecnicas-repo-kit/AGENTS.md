# AGENTS.md

## Mission

Build the internal web application described in `docs/reference/ESPEC_validador_fichas_tecnicas_v2.md`, corrected by the approved decisions and phase gates in `docs/`. The product is a consolidation and pharmacist-validation system for medication master data. It is not a clinical decision-support system.

## Read before work

Before planning or changing code, read:

1. `docs/PROJECT_CONTEXT.md`
2. `docs/DEVELOPMENT_PLAN.md`
3. `docs/DECISION_REGISTER.md`
4. relevant accepted ADRs under `docs/decisions/`
5. the relevant section of the v2 specification

Accepted ADRs override proposed decisions. The v2 specification remains authoritative for closed client decisions and non-negotiable safety constraints. Never silently resolve a conflict: record it in the decision register and propose an ADR.

## Non-negotiable product rules

- Never process patient data.
- Never implement clinical recommendations or treatment advice.
- Never preselect values for `proponer_opciones` or `solo_evidencia`.
- Never persist an extracted proposal without verifiable provenance. Literal FT evidence must match the cited immutable document version exactly.
- Never infer, calculate, convert, round, or normalize a clinical value unless an accepted rule explicitly authorizes it.
- Model repeated blocks explicitly. Do not collapse compositions, indications, routes, frequencies, excipients, links, advice, analytical data, populations, or interactions into one value per field.
- Preserve immutable source-document versions and link every proposal and validation to a specific version.
- Never truncate, drop, overwrite, or coerce source values silently. Produce a diagnostic instead.
- A record with unresolved double-validation discrepancies must not be exported.
- Keep the interface and user-facing validation messages in Spanish.

## Engineering workflow

For every task:

1. Restate the task as an issue-sized objective.
2. Identify applicable requirements, ADRs, risks, and acceptance criteria.
3. Delegate independent read-heavy analysis to subagents when useful.
4. Produce a short execution plan before editing.
5. Use one writing agent per branch or worktree. Do not let parallel agents edit overlapping files.
6. Implement the smallest coherent vertical change.
7. Add or update automated tests.
8. Run the relevant quality commands and report exact results.
9. Update `docs/STATUS.md`, the backlog, traceability, and ADRs when behavior or decisions change.
10. Summarize changed files, tests, residual risks, and the next recommended issue.

## Phase discipline

Do not skip phase gates in `docs/DEVELOPMENT_PLAN.md`. In particular, do not finalize the review UI, extractor, or export model before the canonical-data-model and omeprazole round-trip gates pass.

## Architecture defaults

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic.
- Database: SQLite for the pilot, with portable SQLAlchemy types and migrations.
- Frontend: React, TypeScript, Vite.
- Tests: pytest and Vitest; add integration tests for import/export and policy rules.
- Deployment: Docker Compose from the first executable phase.
- Inference: local OpenAI-compatible server behind an `ExtractorLLM` interface.

Change a default only through an ADR with rationale, alternatives, impact, and migration cost.

## Code review rules

Prioritize correctness, data preservation, clinical-safety boundaries, provenance, versioning, access to repeated rows, export reproducibility, and missing tests. Ignore cosmetic style findings unless they hide a functional issue.

Flag as blocking:

- any path that can store an uncited proposal;
- any UI path that preselects a protected field;
- any data model that cannot represent repeated rows;
- any update that overwrites historical FT text;
- any silent truncation or discarded source row;
- any export that includes unresolved risk validation;
- any code that introduces patient data or clinical advice.

## Commands

Until the scaffold defines canonical commands, inspect the repository and use the documented commands. Once established, keep a single command surface such as `make lint`, `make test`, `make typecheck`, `make verify`, and `docker compose up`. Do not invent parallel command conventions.
