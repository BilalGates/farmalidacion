---
name: pharma-validator-companion
description: Companion workflow for planning, implementing, reviewing, and documenting the Validador de Fichas Técnicas project. Use for any task in this repository involving requirements, decisions, Excel master analysis/import, canonical data modeling, CIMA ingestion and versioning, local LLM extraction, pharmacist review UX, export, double validation, audit, testing, or release planning. Enforces the project's clinical-safety boundaries, phase gates, ADR workflow, provenance, non-loss rules, tests, and traceability. Do not use for unrelated repositories or for clinical decision support.
---

# Validador de Fichas Técnicas — Development Companion

## Purpose

Keep every task aligned with the real source files, accepted decisions, clinical-safety boundaries, and phase gates. Treat the product as a multi-source consolidation and pharmacist-validation system, not as a generic document extractor.

## Required context

Before substantial work, read the applicable repository files in this order:

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/DEVELOPMENT_PLAN.md`
4. `docs/DECISION_REGISTER.md`
5. accepted ADRs under `docs/decisions/`
6. the relevant section of `docs/reference/ESPEC_validador_fichas_tecnicas_v2.md`
7. `docs/SOURCE_INVENTORY.md` for tasks touching source files

Read `references/non-negotiables.md` before implementation or review. Read `references/phase-gates.md` when planning or closing a phase. Read `references/task-workflows.md` for the workflow matching the task type.

## Classify the task

Choose one primary mode:

- **Decision:** a requirement, data relationship, source priority, export rule, or architecture choice is unresolved.
- **Exploration:** inspect code, documents, data, APIs, or failures without changing product behavior.
- **Implementation:** build or change one issue-sized behavior.
- **Review:** independently find correctness, safety, data-loss, regression, or test risks.
- **Phase close:** verify a gate and produce evidence for advancing.

Do not hide a decision inside implementation. If behavior depends on an unresolved choice, create or update an ADR and mark the code as a spike unless the human owner accepts the decision.

## Core workflow

1. State the issue-sized objective and explicit non-goals.
2. Map the task to requirements, decisions, ADRs, phase, and acceptance criteria.
3. Identify risks to cardinality, provenance, immutable versions, clinical-safety policy, export, and audit.
4. Delegate independent read-heavy analysis to specialized subagents when it materially helps.
5. Consolidate their evidence in the main thread before editing.
6. Produce a short execution plan with files, migrations, tests, docs, and rollback.
7. Use one writing agent per branch or worktree.
8. Implement the smallest coherent change.
9. Run the relevant tests and quality checks; report actual commands and results.
10. Update `docs/STATUS.md`, `docs/BACKLOG.md`, `docs/TRACEABILITY_MATRIX.md`, and ADRs when applicable.
11. Return the completion report defined below.

## Delegation rules

Prefer parallel read-only subagents for domain analysis, data profiling, API verification, test design, UX review, security review, and PR review. Avoid simultaneous writes to overlapping files. Use separate worktrees for independent write-heavy tasks and integrate them serially.

Ask subagents for distilled findings with file references, evidence, risks, and tests. Do not flood the main thread with raw logs.

## Completion report

Always report:

1. **Objective and result**
2. **Requirements and decisions applied**
3. **Changed files or artifacts**
4. **Migrations or data impact**
5. **Tests and exact results**
6. **Residual risks or unresolved decisions**
7. **Documentation updated**
8. **Next recommended issue**

If no code was changed, say so explicitly and provide the evidence produced.
