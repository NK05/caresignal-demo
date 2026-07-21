# CareSignal Codex Instructions

## Source of truth

- `CARESIGNAL_MVP_SPEC.md` is the locked product and engineering specification.
- `CHANGES.log` is the shared implementation and validation record.
- Work on one `CS-*` task at a time.
- Do not mark a task Done when required validation fails.

## Role

Codex owns focused implementation, tests, repetitive edits, documentation, cleanup, and validation. Keep changes within the active task boundary and leave a runnable repository.

## Non-negotiable safety boundaries

- Synthetic data only.
- Hypertension follow-up for already diagnosed adults only.
- No diagnosis, treatment selection, prescribing, or medication changes.
- GPT-5.6 may extract, clarify, summarise, and draft. It may not set clinical priority or override deterministic rules.
- Unconfirmed model extraction must never create a blood-pressure reading or clinician task.
- Patient-directed AI drafts require clinician approval before sending.
- Do not claim the WhatsApp simulator is a live WhatsApp integration.
- Do not claim illustrative rules or translations are clinically validated.

## Architecture rules

- Backend is the source of truth for permissions, reading confirmation, rules, task state, and message approval.
- Clinical rule configuration must be deterministic, versioned, explainable, and independent of prompts.
- Keep API keys and secrets server-side and out of logs, fixtures, screenshots, and commits.
- Preserve strict patient isolation and role checks in API tests.
- Prefer the complete P0 journey over optional breadth.

## Validation

- Add tests proportional to every behaviour change.
- Run the narrowest relevant tests during implementation and the required task validation before handoff.
- Record commands and pass/fail results in `CHANGES.log`.

