# Non-negotiable rules

- Never process patient data.
- Never provide treatment recommendations or clinical decision support.
- Never let the model decide a clinical value requiring professional judgment.
- Never preselect `proponer_opciones` or `solo_evidencia`.
- Never persist a textual proposal without literal evidence matching the cited immutable source version.
- Never infer, calculate, convert, round, or normalize clinical values unless an accepted rule authorizes it.
- Never collapse repeated source rows into one value per field.
- Never overwrite historical document text or source batches.
- Never truncate, discard, deduplicate, coerce, or replace data silently.
- Never export records with unresolved required fields, double-validation work, or discrepancies.
- Keep the application useful when extraction degrades to evidence-only.
- Keep user-facing validation UI and messages in Spanish.
