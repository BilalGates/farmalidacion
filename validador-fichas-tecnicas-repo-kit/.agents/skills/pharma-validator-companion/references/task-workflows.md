# Task workflows

## Decision workflow

1. Locate or create the decision ID in `docs/DECISION_REGISTER.md`.
2. Gather evidence from source files, specification, code, provider input, and tests.
3. Create an ADR using `docs/decisions/ADR-TEMPLATE.md`.
4. Present at least two viable alternatives.
5. Include consequences, migration, reversibility, and validation.
6. Keep status `propuesto` until a human accepts it.
7. Update plan, backlog, and traceability after acceptance.

## Exploration workflow

1. Stay read-only.
2. State the exact questions being investigated.
3. Use targeted inspection and reproducible commands.
4. Separate observations, inferences, and recommendations.
5. Return evidence, unresolved questions, and the smallest next issue.

## Implementation workflow

1. Confirm the phase gate allows the work.
2. Read accepted ADRs and define acceptance tests first.
3. Plan migrations, compatibility, error handling, and rollback.
4. Implement one issue-sized behavior.
5. Add tests for success, failure, idempotency, and non-loss where applicable.
6. Run quality checks and fix failures.
7. Update status, backlog, traceability, and operational docs.

## Review workflow

1. Review requirements and ADRs before the diff.
2. Prioritize data loss, cardinality, provenance, versioning, protected prefill, export, audit, and missing tests.
3. Provide severity, file/symbol, reproduction, impact, and safe correction.
4. Avoid style-only findings unless they hide a defect.
5. Recheck after fixes.

## Phase-close workflow

1. Enumerate every gate criterion.
2. Link each criterion to tests, reports, demos, or accepted decisions.
3. Mark unmet items and blocking risks.
4. Do not declare the phase complete with implicit exceptions.
5. Update `docs/STATUS.md` and recommend advance, conditional advance, or stop.
