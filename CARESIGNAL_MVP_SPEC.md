# CareSignal MVP Specification

**Document status:** Build-ready baseline  
**Version:** 1.0  
**Date:** 17 July 2026  
**Target:** OpenAI Build Week 2026 — Apps for Your Life  
**Submission deadline:** 22 July 2026, 00:00 UTC / 02:00 CAT  
**Data policy:** Synthetic demonstration data only  

## 1. Executive summary

CareSignal is a multilingual hypertension follow-up platform for adults who have already been diagnosed with hypertension and are receiving treatment. Patients submit home blood-pressure readings through a lightweight web application or a WhatsApp-compatible conversation channel in English, Shona, or Ndebele. CareSignal confirms the structured information, evaluates it with a transparent deterministic rules engine, and turns concerning patterns or medication-adherence signals into explainable, assigned, time-bound clinician review tasks.

GPT-5.6 supports multilingual message interpretation, structured data extraction, missing-information detection, case summarisation, and draft communication. It does not diagnose hypertension, determine treatment, change medication, or independently classify clinical urgency. All safety-relevant decisions come from versioned deterministic rules and remain subject to clinician review.

The MVP must prove one complete loop:

1. A patient sends a BP reading and adherence context.
2. The patient confirms what the system extracted.
3. A deterministic rule creates a review task with an explicit reason.
4. A clinician owns, reviews, and resolves the task.
5. The patient receives a clinician-approved response in the selected language.
6. Every material action appears in an audit timeline.

The MVP is a workflow prototype, not a medical device and not a production clinical service.

## 2. Product thesis

### 2.1 Problem

Occasional clinic readings may not show what happens between visits. Patients may have repeated abnormal home readings, miss medication, or delay returning to care, while healthcare workers have no timely visibility. A reading log alone does not guarantee that a concerning pattern becomes an owned and completed human action.

### 2.2 Solution

CareSignal creates a shared follow-up loop across patient and clinician channels. It makes each flag explainable, assigns ownership, tracks acknowledgement and resolution, and returns an approved response to the patient.

### 2.3 One-line positioning

> CareSignal turns everyday blood-pressure messages—in English, Shona, or Ndebele—into explainable, prioritised, and trackable clinician follow-up.

### 2.4 Differentiation

CareSignal is not differentiated by BP logging, charts, chat, or threshold alerts alone. Those already exist. Its defensible combination is:

- a familiar low-friction patient channel;
- multilingual and code-switched message interpretation;
- confirmation before health information is recorded;
- deterministic and explainable pattern detection;
- medication-adherence context;
- an operational queue with ownership and workflow state;
- overdue-task escalation;
- clinician-approved multilingual closure.

## 3. Goals and success criteria

### 3.1 MVP goals

- Demonstrate a complete patient-to-clinician-to-patient follow-up loop.
- Support English, Shona, and Ndebele for the constrained demo flows.
- Accept structured app entry and conversational message entry through one shared backend.
- Make every recorded reading patient-confirmed.
- Make every generated task explainable by deterministic rule evidence.
- Keep GPT-5.6 useful but outside the clinical decision boundary.
- Provide a judge-ready hosted demo using synthetic data.
- Provide repeatable setup, seeded scenarios, tests, and a clear README.

### 3.2 Definition of success

The MVP succeeds when a judge can complete the following without developer assistance:

1. Open the hosted demo.
2. Enter as a seeded patient or clinician.
3. Submit or inspect a multilingual reading.
4. See the extraction-confirmation step.
5. See a rule-generated task and its evidence.
6. Assign, review, and resolve the task.
7. Approve a translated follow-up message.
8. Verify the patient sees the resolution.

### 3.3 Non-goals

The MVP does not attempt to prove reduced blood pressure, fewer strokes, reduced hospitalisation, or cost savings. Those require clinical evaluation.

## 4. Scope

### 4.1 Included

- Adults with an existing hypertension diagnosis and treatment plan.
- Synthetic patient and clinician accounts.
- Lightweight responsive web application.
- WhatsApp-compatible conversation workflow.
- Real WhatsApp sandbox integration only if credentials and setup are available without threatening the core build.
- Honest web-based WhatsApp simulator as the guaranteed demo channel.
- English, Shona, and Ndebele language selection.
- Constrained code-switching support.
- Manual or conversational BP reading entry.
- Patient confirmation before persistence.
- Medication-taken question and optional missed-medication reason.
- Small closed symptom/context checklist.
- Reading history.
- Versioned deterministic review rules.
- Clinician task queue.
- Task assignment, acknowledgement, review, resolution, and escalation.
- GPT-5.6 structured extraction, case briefs, missing-information prompts, and response drafts.
- Clinician approval or editing before patient communication.
- Audit timeline.
- Synthetic demonstration data and reset.

### 4.2 Explicitly excluded

- Diagnosing new hypertension.
- Diabetes, HIV, pregnancy-related hypertension, paediatric cases, or general chronic-care management.
- Medication recommendations, dose changes, prescribing, or refill authorisation.
- Open-ended symptom checking.
- Automated medical advice.
- Real patient data.
- Production healthcare deployment.
- Hardware or Bluetooth BP-device integration.
- Hospital, laboratory, insurance, EHR, Cimas, or Health Sync integration.
- Claims that translations are clinically validated.
- SMS and USSD in the MVP.
- Native Android or iOS applications.
- Predictive clinical machine learning.

Any excluded feature requires a post-hackathon scope decision and must not enter the MVP through implementation convenience.

## 5. Users and roles

### 5.1 Patient

An adult already receiving hypertension treatment who records home BP readings and receives follow-up communication.

Patient permissions:

- choose or change language;
- submit a reading;
- confirm or reject extracted information;
- provide adherence and limited context;
- view own reading history;
- view neutral follow-up status;
- receive clinician-approved messages.

Patients cannot view risk tiers intended only for clinical workflow if those labels could be misinterpreted. Patient-facing status language remains neutral and non-diagnostic.

### 5.2 Clinician

A synthetic nurse, doctor, or authorised chronic-care worker.

Clinician permissions:

- view the prioritised review queue;
- filter and sort tasks;
- view patient reading history and rule evidence;
- assign a task to self or another seeded clinician;
- acknowledge and move a task through permitted states;
- record contact attempts and outcomes;
- generate, edit, approve, and send a follow-up message;
- resolve a task.

### 5.3 Demo administrator

A non-production role that can reset seed data and switch demo personas. It cannot change clinical rule thresholds through the public UI.

## 6. Core user journeys

### 6.1 Patient web-app journey

1. Patient opens the demo and selects a seeded patient persona.
2. Patient selects English, Shona, or Ndebele.
3. Patient chooses **Record blood pressure**.
4. Patient enters systolic, diastolic, measurement time, medication status, and optional context.
5. The interface displays a complete confirmation summary.
6. Patient confirms or edits the reading.
7. Backend saves the reading and evaluates deterministic rules.
8. Patient receives a neutral acknowledgement.
9. If a task is created, the patient sees: **Your care team has been notified for review.**
10. Patient later sees the clinician-approved response and review completion status.

### 6.2 Conversational channel journey

1. Patient opens the WhatsApp simulator or sandbox conversation.
2. Patient selects or states a preferred language.
3. Patient sends free text, for example: `I-BP yami ngu-168 over 105. Ngithathe amaphilisi ekuseni.`
4. GPT-5.6 returns a strict structured extraction, not a clinical interpretation.
5. Conversation shows the extracted BP, time, and adherence context.
6. Patient confirms, corrects, or cancels.
7. Only confirmed data is persisted.
8. Deterministic rules evaluate the record.
9. The channel returns a safe template response in the selected language.
10. Approved clinician follow-up returns on the same channel.

### 6.3 Clinician journey

1. Clinician enters the seeded workspace.
2. Dashboard shows open tasks ordered by priority and age.
3. Clinician opens a task.
4. Task displays the exact deterministic reason, readings involved, adherence context, and audit history.
5. GPT-5.6 generates a grounded case brief from the displayed evidence.
6. Clinician assigns and acknowledges the task.
7. Clinician records a contact attempt or review note.
8. Clinician generates a draft follow-up in the patient's preferred language.
9. Clinician edits or approves the message.
10. Clinician records an outcome and resolves the task.
11. Patient receives the approved message.

### 6.4 Escalation journey

1. A seeded urgent-review task remains unacknowledged past its configured demo SLA.
2. The scheduler or demo clock marks the task overdue.
3. The task is visually escalated and an audit event is recorded.
4. No automatic patient diagnosis or treatment message is sent.

## 7. Product surfaces and screens

### 7.1 Public/demo landing

Required elements:

- one-sentence product definition;
- **Patient demo** and **Clinician demo** actions;
- synthetic-data notice;
- non-diagnostic notice;
- reset-demo control;
- project architecture or **How it works** summary;
- visible language options.

### 7.2 Patient home

- greeting and preferred language;
- record-reading action;
- latest confirmed reading;
- recent reading list;
- current follow-up status;
- latest approved care-team message;
- clear emergency disclaimer directing users to local emergency services in a real deployment, without presenting the demo as an emergency service.

### 7.3 Structured reading form

- systolic integer field;
- diastolic integer field;
- measurement date/time;
- medication taken: yes / no / prefer not to say;
- if no, optional structured reason;
- small context checklist;
- free-text note, explicitly optional;
- review-and-confirm step;
- cancel action.

### 7.4 Conversation simulator

- recognisable but non-infringing messaging interface;
- channel labelled **WhatsApp-compatible demo** unless using the real sandbox;
- language selection;
- message input;
- extraction confirmation card;
- correction actions;
- system notices distinguishing templates from AI-generated drafts;
- conversation history.

### 7.5 Clinician dashboard

Summary cards:

- unassigned;
- awaiting acknowledgement;
- in review;
- overdue;
- resolved today.

Queue fields:

- patient synthetic identifier;
- task priority;
- concise flag reason;
- latest reading;
- medication context indicator;
- assigned owner;
- status;
- task age;
- overdue state.

Filters:

- priority;
- status;
- owner;
- overdue;
- language;
- medication-adherence signal.

### 7.6 Task detail

- patient summary;
- preferred language and channel;
- reading timeline;
- deterministic rule evidence;
- adherence context;
- GPT-5.6 case brief with **AI-generated draft** label;
- assignment and status controls;
- contact-attempt form;
- outcome field;
- multilingual response composer;
- approval/send control;
- audit timeline.

### 7.7 Patient detail

- synthetic demographics relevant to the demo only;
- reading history;
- active and resolved tasks;
- adherence-response history;
- approved messages;
- no diagnosis editor and no medication editor.

## 8. Workflow and state machines

### 8.1 Reading states

`PENDING_CONFIRMATION → CONFIRMED → EVALUATED`

Alternative terminal states:

- `CORRECTED` creates a revised pending record;
- `REJECTED` stores no clinical values beyond minimal audit metadata;
- `CANCELLED` stores no clinical values beyond minimal audit metadata.

Invariant: unconfirmed model extraction must never enter the clinical reading history or trigger rules.

### 8.2 Task states

`OPEN → ASSIGNED → IN_REVIEW → RESOLVED`

Permitted supporting transitions:

- `OPEN → ASSIGNED`
- `ASSIGNED → OPEN` only through explicit unassignment
- `ASSIGNED → IN_REVIEW`
- `IN_REVIEW → ASSIGNED` if returned for another reviewer
- `IN_REVIEW → RESOLVED`
- `RESOLVED → IN_REVIEW` only through explicit reopen action with audit reason

Derived task flags:

- `UNACKNOWLEDGED`
- `OVERDUE`
- `ESCALATED`

These are not independent workflow states.

### 8.3 Message states

`DRAFT → APPROVED → SENT`

Alternative states:

- `REJECTED`
- `DELIVERY_FAILED`

Invariant: patient-directed AI drafts cannot be sent before clinician approval. Fixed safety templates may be sent automatically after confirmation because they contain no personalised medical advice.

## 9. Deterministic rules engine

### 9.1 Purpose

The rules engine decides whether a confirmed reading or pattern creates a clinician review task. It must be deterministic, versioned, tested, and explainable.

### 9.2 Rule categories

The MVP supports configurable examples of:

- single-reading threshold rule;
- repeated-elevation rule;
- sustained-pattern rule;
- rate-of-change or worsening-trend rule;
- missed-reading rule;
- medication-adherence follow-up rule;
- context/symptom escalation rule using closed structured inputs only.

### 9.3 Rule output contract

Each triggered rule returns:

```json
{
  "rule_id": "string",
  "rule_version": "string",
  "priority": "routine|watch|needs_review|urgent_review",
  "title": "short non-diagnostic label",
  "reason": "plain factual explanation",
  "evidence_reading_ids": ["uuid"],
  "evidence": {
    "observed_values": [],
    "window_start": "ISO-8601",
    "window_end": "ISO-8601"
  },
  "sla_minutes": 0,
  "source_reference": "configured guideline or demo rule reference"
}
```

### 9.4 Threshold governance

- No threshold may be embedded in a prompt.
- Thresholds live in version-controlled configuration.
- The UI displays the active rule version and source reference.
- Seeded demo thresholds must be labelled **Illustrative prototype configuration—not clinically validated for deployment**.
- Before any real deployment, a Zimbabwe-appropriate protocol and named clinical governance process are mandatory.

### 9.5 Deduplication

The engine must avoid creating multiple open tasks for the same patient and materially identical rule evidence. If an existing open task covers the rule, new evidence appends to that task and creates an audit event. A higher-priority rule may raise the task priority.

## 10. GPT-5.6 contracts

### 10.1 Allowed AI functions

1. **Message extraction** — transform a multilingual patient message into structured candidate fields.
2. **Clarification generation** — ask for missing or ambiguous non-diagnostic information.
3. **Case brief** — summarise confirmed readings, rule evidence, adherence context, and workflow history.
4. **Draft patient communication** — draft a message grounded only in clinician-provided outcome and approved templates.
5. **Language adaptation** — produce English, Shona, or Ndebele drafts for clinician review.

### 10.2 Prohibited AI functions

- diagnosis;
- treatment selection;
- medication or dose instruction;
- overriding the deterministic priority;
- inventing readings, symptoms, adherence, or patient history;
- deciding whether emergency care is required;
- sending personalised patient communication without approval;
- claiming translation validation.

### 10.3 Extraction schema

```json
{
  "language": "en|sn|nd|mixed|unknown",
  "systolic": 0,
  "diastolic": 0,
  "measurement_time_text": "string|null",
  "medication_taken": "yes|no|unknown|prefer_not_to_say",
  "missed_medication_reason": "string|null",
  "context_codes": ["string"],
  "unstructured_note": "string|null",
  "missing_fields": ["string"],
  "ambiguities": ["string"],
  "requires_confirmation": true
}
```

Server validation rejects:

- missing systolic or diastolic values;
- non-integer values;
- values outside configurable plausibility bounds;
- unsupported context codes;
- `requires_confirmation: false` from the model;
- additional unexpected fields.

### 10.4 Grounded case-brief schema

```json
{
  "summary": "string",
  "timeline_points": ["string"],
  "rule_explanation": "string",
  "adherence_context": "string|null",
  "missing_information": ["string"],
  "source_record_ids": ["uuid"],
  "safety_note": "AI-generated workflow summary; verify against source records."
}
```

The backend verifies that every source record ID belongs to the current patient and is visible to the requesting clinician.

### 10.5 Failure behaviour

If GPT-5.6 is unavailable, times out, produces invalid structured output, or has low-confidence ambiguity:

- the app remains usable through the structured form;
- raw conversational submission is not persisted as a reading;
- the patient is asked to use structured entry or try again;
- deterministic rules and clinician workflows continue functioning;
- a visible, non-alarming error is shown;
- no fabricated fallback summary is produced.

## 11. Language and content requirements

### 11.1 Supported languages

- English (`en`)
- Shona (`sn`)
- Ndebele (`nd`)

### 11.2 MVP language boundary

The interface shell and fixed templates use reviewed translation dictionaries. GPT-5.6 handles constrained free-text extraction and drafts. A fluent speaker must review all demo scripts and high-stakes fixed text before recording the submission video.

### 11.3 Code-switching

The extraction function may return `mixed`. The confirmation screen always shows the numerical interpretation explicitly. If meaning remains ambiguous, the system asks a clarification question rather than guessing.

### 11.4 Neutral notifications

Because patients may share phones, message previews and outbound notifications must avoid sensitive detail. Example: **You have a new CareSignal update. Open the conversation to view it.**

### 11.5 Safety wording

Required persistent concepts:

- CareSignal does not diagnose conditions.
- CareSignal does not replace a healthcare professional.
- The demonstration is not an emergency service.
- The prototype uses synthetic data.

## 12. WhatsApp channel strategy

### 12.1 Required architecture

All patient channels use the same internal message service:

```text
Channel adapter → conversation service → extraction/confirmation → reading service
               → rules engine → task service → approved outbound message
```

### 12.2 Guaranteed demo path

Build a web-based WhatsApp-compatible simulator that exercises the real conversation, extraction, confirmation, rules, and messaging services. It must be clearly labelled as a simulator.

### 12.3 Optional real integration

If Meta WhatsApp Cloud API or another authorised sandbox is available, add an adapter implementing:

- webhook verification;
- inbound text normalisation;
- sender-to-patient mapping for seeded demo numbers;
- outbound approved template/text delivery;
- idempotency by provider message ID;
- signature verification where supported;
- delivery-status recording.

The project must not depend on real WhatsApp approval for core judging.

## 13. Recommended technical architecture

### 13.1 Repository

Monorepo:

```text
caresignal/
├── AGENTS.md
├── CHANGES.log
├── README.md
├── apps/
│   ├── web/                 # Next.js, TypeScript, Tailwind, shadcn/ui
│   └── api/                 # FastAPI, Python, SQLAlchemy, Pydantic
├── docs/
│   ├── MVP_SPEC.md
│   ├── SAFETY.md
│   ├── AI_USAGE.md
│   └── DEMO_SCRIPT.md
├── packages/
│   └── contracts/           # Generated or shared API schemas
└── tests/
    └── e2e/                 # Playwright complete journeys
```

### 13.2 Frontend

- Next.js with TypeScript.
- Tailwind CSS and shadcn/ui.
- Responsive web experience; mobile-first patient surfaces and desktop-first clinician surfaces.
- Server-state library only if needed; avoid unnecessary framework additions.
- Accessible components and keyboard operation.

### 13.3 Backend

- Python FastAPI.
- Pydantic request/response validation.
- SQLAlchemy ORM.
- SQLite for the deterministic local and hosted hackathon demo if supported by hosting; PostgreSQL-compatible schema for later migration.
- OpenAI official SDK with structured outputs.
- Background escalation via an explicit endpoint or lightweight scheduler appropriate to the hosting environment.

### 13.4 Deployment

- Frontend: Vercel or equivalent.
- Backend: a Python-capable managed host.
- Database: demo-safe persistent store or deterministic seeded store.
- Provide a one-action demo reset.
- Never place API keys in the client.

### 13.5 Authentication for the hackathon

Use seeded demo personas with controlled role-switching. Do not spend the build window on production identity. Route guards and backend role checks remain mandatory. Clearly label demo access as non-production.

## 14. Data model

### 14.1 User

- `id`
- `display_name`
- `role`: patient | clinician | demo_admin
- `preferred_language`
- `active`
- timestamps

### 14.2 PatientProfile

- `id`
- `user_id`
- `synthetic_identifier`
- `preferred_channel`: app | whatsapp_simulator | whatsapp_sandbox
- `consent_demo_acknowledged`
- timestamps

Do not store real addresses, national IDs, HIV status, or unnecessary demographics.

### 14.3 ClinicianProfile

- `id`
- `user_id`
- `display_role`
- timestamps

### 14.4 ReadingSubmission

- `id`
- `patient_id`
- `channel`
- `original_message` nullable
- `candidate_payload` JSON
- `status`
- `language`
- `model_request_id` nullable
- timestamps

### 14.5 BloodPressureReading

- `id`
- `patient_id`
- `submission_id`
- `systolic`
- `diastolic`
- `measured_at`
- `medication_taken`
- `missed_medication_reason_code` nullable
- `context_codes` JSON/array
- `note` nullable
- `confirmed_at`
- timestamps

### 14.6 RuleEvaluation

- `id`
- `patient_id`
- `reading_id`
- `rule_id`
- `rule_version`
- `triggered`
- `priority`
- `reason`
- `evidence` JSON
- `source_reference`
- `evaluated_at`

### 14.7 ReviewTask

- `id`
- `patient_id`
- `priority`
- `status`
- `assigned_clinician_id` nullable
- `primary_rule_evaluation_id`
- `opened_at`
- `acknowledged_at` nullable
- `due_at` nullable
- `resolved_at` nullable
- `outcome_code` nullable
- `outcome_note` nullable
- `reopened_count`
- timestamps

### 14.8 TaskEvidence

- `task_id`
- `rule_evaluation_id`
- unique constraint across both fields

### 14.9 ContactAttempt

- `id`
- `task_id`
- `clinician_id`
- `channel`
- `outcome_code`
- `note`
- `attempted_at`

### 14.10 PatientMessage

- `id`
- `patient_id`
- `task_id` nullable
- `direction`: inbound | outbound
- `channel`
- `language`
- `content`
- `generation_type`: fixed_template | ai_draft | clinician_authored
- `approval_status`
- `approved_by` nullable
- `approved_at` nullable
- `sent_at` nullable
- `delivery_status`
- timestamps

### 14.11 AuditEvent

- `id`
- `actor_user_id` nullable for system events
- `patient_id` nullable
- `entity_type`
- `entity_id`
- `event_type`
- `metadata` JSON containing no secret values
- `created_at`

## 15. API contract

All endpoints are versioned under `/api/v1`.

### 15.1 Demo and session

- `POST /demo/reset`
- `POST /demo/session` — select seeded persona
- `GET /me`

### 15.2 Patient

- `GET /patient/profile`
- `PATCH /patient/preferences`
- `GET /patient/readings`
- `POST /patient/submissions/structured`
- `POST /patient/submissions/message`
- `GET /patient/submissions/{id}`
- `POST /patient/submissions/{id}/confirm`
- `POST /patient/submissions/{id}/correct`
- `POST /patient/submissions/{id}/reject`
- `GET /patient/follow-up`
- `GET /patient/messages`

### 15.3 Clinician

- `GET /clinician/dashboard`
- `GET /clinician/tasks`
- `GET /clinician/tasks/{id}`
- `POST /clinician/tasks/{id}/assign`
- `POST /clinician/tasks/{id}/acknowledge`
- `POST /clinician/tasks/{id}/start-review`
- `POST /clinician/tasks/{id}/contact-attempts`
- `POST /clinician/tasks/{id}/draft-message`
- `POST /clinician/tasks/{id}/approve-message`
- `POST /clinician/tasks/{id}/resolve`
- `POST /clinician/tasks/{id}/reopen`
- `GET /clinician/patients/{id}`

### 15.4 Channel webhook

- `GET /channels/whatsapp/webhook` — optional verification
- `POST /channels/whatsapp/webhook` — optional inbound/status events
- `POST /channels/simulator/messages`

### 15.5 System

- `POST /system/escalations/run` — protected demo scheduler endpoint
- `GET /health`

## 16. Security, privacy, and safety

### 16.1 Demo controls

- Synthetic data only.
- Prominent synthetic-data banner.
- No production sign-up.
- No real phone numbers required.
- Seeded identities must be fictional.
- Reset removes all mutable demo records and restores the seed state.

### 16.2 Access control

- Backend enforces patient versus clinician permissions.
- Patients can access only their own records.
- Clinicians can access only the seeded clinic dataset.
- Demo administrator reset is protected against accidental public invocation.
- Every task mutation is audited.

### 16.3 AI privacy

- Send only the minimum necessary synthetic fields to GPT-5.6.
- Do not send secrets, tokens, or internal access-control metadata.
- Record request correlation IDs and model name, not hidden reasoning.
- Prompts instruct the model to avoid diagnosis and medication advice.

### 16.4 Clinical safety

- The prototype never presents itself as an emergency service.
- Patient-facing messages use approved templates or clinician-approved drafts.
- No medication-changing UI exists.
- No diagnosis field exists.
- AI errors cannot persist readings without confirmation.
- Rules cannot be modified by prompt injection or patient text.

## 17. Accessibility and low-data requirements

- Mobile-first patient pages.
- Functional at 320 px width.
- Large touch targets.
- Plain-language labels.
- No essential information conveyed by colour alone.
- Keyboard-accessible clinician interface.
- Visible focus states.
- Semantic form labels and error summaries.
- Avoid autoplay media and large imagery.
- Keep initial patient route bundle and payloads small; measure rather than claim a specific data cost.
- Cache fixed language dictionaries.
- Provide clear retry behaviour for intermittent connectivity.
- Do not clear a patient's unsent form after a network failure.

## 18. Seeded demo scenarios

### Scenario A — stable reading

- Patient: Tariro Moyo (synthetic)
- Language: English
- Channel: structured app
- Result: reading confirmed and stored; no new clinician task.

### Scenario B — repeated concerning pattern

- Patient: Rudo Ncube (synthetic)
- Language: Ndebele
- Channel: conversation simulator
- Input includes BP reading and confirmation that medication was taken.
- Prior seeded readings create a repeated-pattern rule trigger.
- Result: `NEEDS_REVIEW` task with explicit evidence.
- Clinician assigns, reviews, drafts Ndebele follow-up, approves, and resolves.

### Scenario C — missed medication context

- Patient: Tawanda Chikore (synthetic)
- Language: Shona
- Channel: conversation simulator
- Input includes BP reading and missed medication due to unavailable refill.
- Result: adherence follow-up task; system does not tell patient to change or double medication.

### Scenario D — overdue escalation

- Patient: Nomsa Dube (synthetic)
- Language: Ndebele
- Task seeded just before demo SLA expiration.
- Result: scheduler marks it overdue/escalated and records an audit event.

## 19. Acceptance criteria

### 19.1 Critical P0 criteria

- [ ] A patient can submit a structured reading and confirm it.
- [ ] A conversational message can be extracted into the strict schema.
- [ ] Unconfirmed extraction cannot create a reading or task.
- [ ] English, Shona, and Ndebele demo messages complete the confirmation flow.
- [ ] Deterministic evaluation produces a versioned explanation.
- [ ] Repeated evidence does not create duplicate open tasks.
- [ ] A clinician can assign, acknowledge, review, and resolve a task.
- [ ] A patient-directed AI draft cannot be sent without clinician approval.
- [ ] A resolved message appears on the patient's selected channel.
- [ ] Overdue-task escalation is visible and audited.
- [ ] Patient and clinician access boundaries are enforced by the API.
- [ ] The demo resets to a deterministic seed state.
- [ ] The hosted application can complete Scenario B end to end.
- [ ] No diagnosis or medication-change control exists.

### 19.2 P1 criteria

- [ ] Clinician filters work by priority, status, owner, language, and overdue state.
- [ ] AI failure falls back to structured reading entry.
- [ ] Correction and rejection flows work.
- [ ] Contact attempts appear in the timeline.
- [ ] Mobile patient pages and desktop clinician pages pass visual checks.
- [ ] Core workflows meet basic WCAG-oriented keyboard and labelling checks.

### 19.3 Optional P2 criteria

- [ ] Real WhatsApp sandbox adapter.
- [ ] Streaming AI draft generation.
- [ ] Exportable synthetic case summary.
- [ ] Additional visual analytics that do not displace P0 work.

P2 work begins only after all P0 criteria pass in the deployed environment.

## 20. Test plan

### 20.1 Unit tests

Rules engine:

- each rule triggers on its configured fixture;
- near-boundary non-trigger fixtures;
- time-window handling;
- rule version output;
- evidence record IDs;
- deduplication and priority elevation;
- missed-reading and adherence rules;
- no prompt or AI dependency.

AI contracts:

- valid English, Shona, Ndebele, and mixed inputs;
- ambiguous numbers;
- missing systolic or diastolic values;
- extra unexpected fields;
- attempts to request diagnosis or medication advice;
- malformed model output;
- timeout and fallback.

State machines:

- valid transitions;
- invalid transitions rejected;
- approval required before send;
- reopen requires reason;
- audit event created for each mutation.

### 20.2 API integration tests

- patient isolation;
- clinician role enforcement;
- confirmation transaction creates reading and evaluation atomically;
- duplicate webhook idempotency;
- task creation and evidence linking;
- message approval and send;
- demo reset;
- escalation endpoint protection.

### 20.3 End-to-end tests

Required Playwright stories:

1. Structured English submission with no task.
2. Ndebele conversational submission through confirmation to task creation.
3. Clinician assignment, review, approved response, and resolution.
4. Shona missed-medication context preserved without medication advice.
5. Unconfirmed AI extraction never appears in clinician history.
6. Patient cannot access another patient.
7. Overdue task escalates.
8. Demo reset restores initial state.

### 20.4 Manual safety QA

- prompts asking the bot to diagnose;
- prompts asking whether to stop, double, or change medicine;
- fabricated readings in natural language;
- code-switched ambiguous inputs;
- shared-phone notification privacy;
- translation review by fluent speakers;
- outage behaviour;
- all claims checked against implemented behaviour.

## 21. Observability

The MVP records:

- request IDs;
- API errors;
- model call success/failure and latency;
- structured-output validation failures;
- rule evaluations;
- task transitions;
- message approval and delivery status;
- demo reset events.

Never log secrets or unnecessary message content. Provide a simple developer diagnostics view or structured server logs sufficient for judging and debugging.

## 22. Delivery plan and task IDs

### Day 1 — foundation and core data loop

- `CS-001` Scaffold monorepo, instructions, environment templates, and health checks.
- `CS-002` Implement schema, migrations, seed data, and demo reset.
- `CS-003` Implement structured patient reading and confirmation.
- `CS-004` Implement deterministic rules engine and unit tests.
- `CS-005` Implement task creation, deduplication, and state machine.

Exit condition: structured reading can create an explainable clinician task.

### Day 2 — clinician workflow

- `CS-006` Build clinician dashboard and queue.
- `CS-007` Build task detail, assignment, acknowledgement, review, and resolution.
- `CS-008` Build contact attempts, approved messages, and audit timeline.
- `CS-009` Complete the English end-to-end flow and Playwright test.

Exit condition: Scenario B works without AI or multilingual input.

### Day 3 — GPT-5.6 and multilingual channel

- `CS-010` Implement structured GPT-5.6 extraction and fallback.
- `CS-011` Build conversation simulator using the shared channel service.
- `CS-012` Add English, Shona, and Ndebele dictionaries and reviewed demo scripts.
- `CS-013` Implement grounded case briefs and clinician-approved response drafts.
- `CS-014` Add multilingual and failure-path tests.

Exit condition: the complete Ndebele and Shona demo scenarios pass.

### Day 4 — hardening and submission assets

- `CS-015` Implement and demonstrate overdue escalation.
- `CS-016` Run safety, accessibility, responsive, and cross-role QA.
- `CS-017` Deploy, validate, and lock the hosted demo.
- `CS-018` Complete README, AI usage notes, safety notes, and sample data.
- `CS-019` Write and rehearse the under-three-minute demo.
- `CS-020` Record/upload video and complete Devpost submission fields.
- `CS-021` Retrieve and record the required `/feedback` Codex Session ID.

Exit condition: deployed P0 flow, passing tests, accessible repo, public video, and complete submission.

## 23. Development operating rules

- Work on one task ID at a time.
- Record meaningful changes and validation in `CHANGES.log`.
- Do not mark a task Done if its required validation fails.
- Backend is the source of truth for task states, permissions, confirmations, rule results, and message approval.
- Do not add a feature that is not in the Included scope without updating this specification first.
- Do not represent simulator behaviour as live WhatsApp integration.
- Do not represent synthetic or illustrative rules as clinically validated.
- Preserve a runnable build after every completed task.
- Prioritise the end-to-end P0 story over breadth or visual extras.

## 24. Devpost submission alignment

### Category

**Apps for Your Life** — the primary value is patient access and everyday health follow-up, with a clinician workspace required to close the loop.

### Required deliverables

- Working hosted project.
- Project name and edited human-authored description.
- Public YouTube demo under three minutes.
- Voiceover explaining the product, Codex usage, and GPT-5.6 usage.
- Public repository with an appropriate licence, or private repository shared with the required judging addresses.
- README with setup, sample data, testing path, AI usage, and safety boundaries.
- Required `/feedback` Codex Session ID from the principal build session.

### Judging narrative

**Technological implementation:** multilingual structured extraction, deterministic rules, channel adapter, stateful clinical workflow, and safe AI failure behaviour.  
**Design:** one coherent patient-to-clinician-to-patient loop across accessible channels.  
**Potential impact:** earlier visibility and accountable follow-up for treated hypertension in constrained settings; no unproven outcome claims.  
**Quality of idea:** the innovation is the localised closed-loop combination, not BP logging or chat alone.

## 25. Demo video outline

Target length: 2 minutes 40 seconds.

1. **0:00–0:20 — Problem:** occasional clinic readings and invisible home patterns.
2. **0:20–0:50 — Patient:** Ndebele or Shona message, extraction, and confirmation.
3. **0:50–1:15 — Deterministic safety:** explainable rule and task creation.
4. **1:15–1:55 — Clinician:** case brief, assignment, review, approved response, resolution.
5. **1:55–2:15 — Patient closure:** response arrives in preferred language.
6. **2:15–2:35 — Technical implementation:** GPT-5.6 boundaries, Codex build workflow, tests.
7. **2:35–2:40 — Closing:** one-line positioning.

## 26. Evidence and assumptions

### 26.1 Evidence supporting the direction

- WHO reports a substantial hypertension burden in Zimbabwe.
- Established guidance recognises home or ambulatory readings as useful for confirming and monitoring blood pressure.
- Published reviews support the credibility of remote monitoring plus healthcare-provider involvement, while results vary across settings.
- Zimbabwean digital-access research supports WhatsApp as a familiar channel but also shows internet access can reproduce inequity.
- A local clinician interview directly supported remote reading visibility, earlier recall, and medication-adherence context.

### 26.2 Unverified assumptions

- The exact queue structure fits a real Zimbabwean clinic's staffing and accountability model.
- Shona and Ndebele model performance is adequate beyond the constrained demo cases.
- Patients will consistently report medication adherence accurately.
- A WhatsApp-based workflow will be acceptable for sensitive health communication.
- A suitable local clinical protocol can govern thresholds in a real deployment.

These assumptions must not be presented as established facts.

### 26.3 Reference links

- WHO Zimbabwe health data: https://data.who.int/countries/716
- WHO hypertension overview: https://www.who.int/news-room/fact-sheets/detail/hypertension
- WHO HEARTS hypertension protocol resources: https://www.who.int/publications/i/item/WHO-NMH-NVI-19-8
- NICE hypertension recommendations: https://www.nice.org.uk/guidance/ng136/chapter/recommendations
- Zimbabwe digital-access study: https://www.jmir.org/2024/1/e52670
- OpenAI Build Week: https://openai.devpost.com/

## 27. Final build decision

**GO with the locked MVP.**

The project remains viable only if the complete confirmation-to-resolution loop is implemented and tested. If time becomes constrained, remove optional integration and visual enhancements before reducing the core workflow, safety boundary, or submission quality.

