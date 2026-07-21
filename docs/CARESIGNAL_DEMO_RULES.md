# CareSignal illustrative demo rules

Version: `demo-2026.07.1`

These values exist only to demonstrate deterministic workflow mechanics with fictional data. They
are not a Zimbabwe clinical protocol, are not clinically validated, and must not be used for
diagnosis, treatment, medication changes, or real-world triage.

Before any real deployment, the entire configuration requires approval by a named Zimbabwean
clinical-governance body against an applicable, current protocol. The approved source, version,
effective date, owners, review date, and change history must replace this file's demo values.

## Versioned demonstration configuration

| Rule | Demonstration marker | Workflow priority | Demo SLA |
| --- | --- | --- | --- |
| Single reading | Systolic ≥180 or diastolic ≥120 | `urgent_review` | 30 minutes |
| Repeated pattern | At least 3 readings in 7 days with systolic ≥150 or diastolic ≥95 | `needs_review` | 240 minutes |
| Sustained average | At least 3 readings in 14 days averaging systolic ≥145 or diastolic ≥90 | `needs_review` | 480 minutes |
| Worsening pattern | At least 3 readings in 7 days with oldest-to-newest increase of systolic ≥10 or diastolic ≥8 | `watch` | 720 minutes |
| Medication follow-up | Confirmed structured answer `medication_taken=no` | `needs_review` | 1,440 minutes |
| Context follow-up | Confirmed closed code `feeling_unwell` | `needs_review` | 120 minutes |
| Expected reading gap | Last confirmed reading was at least 7 days ago | `watch` | 1,440 minutes |

Priorities are internal workflow labels. They are not diagnoses and are not shown to patients.
Every evaluation records the rule version, factual inputs, configured marker, reading IDs, result,
and this source reference. GPT does not set, change, or override any result.
