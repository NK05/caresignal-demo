# CareSignal

CareSignal is a multilingual hypertension follow-up prototype for OpenAI Build Week 2026. It turns confirmed home blood-pressure submissions into explainable, assigned, and trackable clinician follow-up tasks.

This repository is a synthetic-data demonstration. It is not a medical device, does not diagnose conditions, does not recommend medication changes, and is not an emergency service.

## Repository structure

```text
apps/web/       Next.js patient and clinician experience
apps/api/       FastAPI application and deterministic domain services
docs/           Safety, AI usage, and demo documentation
tests/e2e/      End-to-end user journeys
```

The locked product and engineering boundary is in [CARESIGNAL_MVP_SPEC.md](./CARESIGNAL_MVP_SPEC.md).

## Prerequisites

- Node.js 24+
- npm 11+
- Python 3.12+

## Environment

Copy `.env.example` to `.env.local` and configure local values. Never commit `.env.local` or any API key.

The OpenAI API is used only for constrained multilingual extraction and clinician-support drafts. Deterministic code owns all rule evaluation and workflow state.

## Web application

```bash
npm install
npm run dev:web
```

Open http://localhost:3000. The frontend health endpoint is available at http://localhost:3000/api/health.

## API

```bash
python3 -m venv .venv
.venv/bin/pip install -e 'apps/api[dev]'
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
.venv/bin/uvicorn app.main:app --app-dir apps/api --reload
```

Open http://localhost:8000. The API health endpoint is available at http://localhost:8000/api/v1/health.

Local startup creates and seeds a SQLite database when `CARESIGNAL_AUTO_BOOTSTRAP=true`.
The seed contains only fictional patients and clinicians and covers stable, repeated-elevation,
missed-medication, and urgent-review demonstration paths. It is illustrative and not clinically
validated.

The protected `POST /api/v1/demo/reset` endpoint restores the synthetic baseline. Configure a
private `CARESIGNAL_DEMO_RESET_TOKEN` and send it in the `X-Demo-Reset-Token` header; never expose
that value in browser code or commit it to source.

### Structured patient-reading flow

Select a fictional persona with `POST /api/v1/demo/session`, then send the returned non-production
token in the `X-Demo-Session` header. This is deliberate hackathon persona switching, not a
production authentication system.

The structured flow is:

1. `POST /api/v1/patient/submissions/structured` creates a `pending_confirmation` candidate.
2. `GET /api/v1/patient/submissions/{id}` returns the review summary for that patient only.
3. `POST /api/v1/patient/submissions/{id}/confirm` revalidates the candidate and atomically creates
   the blood-pressure reading.
4. `POST .../correct` replaces the candidate with a revised pending submission; `POST .../reject`
   discards its unconfirmed clinical values.
5. `GET /api/v1/patient/readings` returns only the selected patient's confirmed history.

Configured BP bounds are broad input-plausibility checks, not diagnostic or clinical-priority
thresholds. Confirmation runs the deterministic rule engine in the same database transaction as
reading creation. GPT does not participate in structured entry, confirmation, rule evaluation, or
priority selection.

### Conversation channel

Open http://localhost:3000/patient/conversation for the WhatsApp-compatible simulator. The page is
explicitly labelled as a simulator unless a complete Meta test configuration is active. It uses the
same backend conversation service as the optional Meta adapter and provides history, free-text entry,
an explicit extracted-value card, and **Confirm**, **Correct**, and **Cancel** actions.

The patient API exposes:

- `GET /api/v1/patient/conversation` for patient-isolated history and the current pending candidate;
- `POST /api/v1/patient/conversation/messages` for a new message or the deterministic text commands
  `CONFIRM`, `CORRECT`, and `CANCEL`;
- `POST /api/v1/patient/conversation/submissions/{id}/{confirm|cancel}` for simulator actions.

Both the simulator and Meta adapter use GPT-5.6 Structured Outputs to extract only the locked reading
fields. The server separately validates BP plausibility, timestamp format, medication context,
context codes, and the mandatory confirmation flag.

A complete and valid extraction creates only a `pending_confirmation` submission. It cannot create
a blood-pressure reading, rule evaluation, or clinician task until the patient uses the existing
confirmation endpoint. Missing fields return a fixed non-diagnostic clarification. Ambiguity,
timeout, API failure, malformed output, or failed server validation returns a neutral retry or
structured-form fallback without creating a submission or fabricating an answer. Rejected or
corrected conversational candidates erase the unconfirmed raw message and extracted values.

The model request uses the Responses API with a typed Pydantic output contract, API-side response
storage disabled, and a configurable timeout. Logs contain only operational metadata such as
latency, request ID, counts, and error type—not the API key, patient message, or exception text.

#### Optional Meta WhatsApp Cloud API test channel

The simulator requires no Meta account and remains the guaranteed demo path. A real Meta test number
can be connected without changing the conversation or clinical workflow:

1. Create a Meta developer app, add WhatsApp, and use the test phone number and recipient offered in
   the WhatsApp API setup screen.
2. Expose the API over HTTPS and configure this callback URL in Meta:
   `https://<public-api>/api/v1/channels/whatsapp/webhook`.
3. Generate your own random webhook verification value and use the same value for Meta and
   `WHATSAPP_VERIFY_TOKEN`.
4. Set the server-only variables below in `.env.local`. Do not paste tokens or the app secret into
   chat, browser code, screenshots, fixtures, or commits.

```dotenv
WHATSAPP_CLOUD_API_ENABLED=true
WHATSAPP_CLOUD_API_VERSION=v23.0
WHATSAPP_PHONE_NUMBER_ID=<test-phone-number-id>
WHATSAPP_ACCESS_TOKEN=<temporary-or-system-user-token>
WHATSAPP_VERIFY_TOKEN=<your-random-verify-value>
WHATSAPP_APP_SECRET=<meta-app-secret>
WHATSAPP_DEMO_PHONE_MAP={"263771234567":"10000000-0000-4000-8000-000000000002"}
```

Replace the fictional phone number with the digits-only number registered as the Meta test recipient.
The mapped UUID is the seeded synthetic Rudo patient; never map a real patient's identity or send real
health data. If Meta shows a different supported Graph API version, set that version explicitly.

The adapter verifies webhook challenges and HMAC signatures, accepts inbound text only, maps only
configured demo senders, deduplicates provider message IDs, sends the fixed confirmation/clarification
response, records provider delivery status, and routes clinician-approved responses back through the
same channel. Failed sends are retained as failed or approved for safe review; they do not fabricate
delivery. The code and automated provider-boundary tests are complete, but a live Meta request still
requires your credentials and an HTTPS deployment. Meta account eligibility, temporary-token expiry,
test-recipient limits, and any production messaging charges remain external platform constraints.

The active ruleset is `demo-2026.07.1`. Its version-controlled values and limitations are documented
in [docs/CARESIGNAL_DEMO_RULES.md](./docs/CARESIGNAL_DEMO_RULES.md). These are illustrative workflow
markers, not a Zimbabwe clinical protocol and not clinically validated.

Triggered evaluations now create internal clinician review tasks in the same confirmation
transaction. An active task is reused only for the same patient, rule ID, and rule version; new
evidence is linked and priority can move only upward. Resolved tasks remain closed and later evidence
creates a new task. Patients receive only the neutral notification that their care team was notified,
not the internal priority or rule rationale.

### Clinician dashboard

Open http://localhost:3000/clinician for the read-only synthetic clinician workspace. The dashboard
shows backend-computed summary counts and active review tasks ordered by internal priority and age.
It includes the specified priority, status, owner, overdue, language, and medication-context filters.

The clinician API requires a fictional clinician persona in `X-Demo-Session`:

- `GET /api/v1/clinician/dashboard` returns summary counts, filtered active tasks, and available
  synthetic owners.
- `GET /api/v1/clinician/tasks` returns the same backend-owned queue without summary cards and accepts
  query parameters for `priority`, `status`, `owner`, `overdue`, `language`, and
  `medication_adherence_signal`.

Configure `CARESIGNAL_DEMO_CLINICIAN_USER_ID` for the server-side web proxy. This is non-production
persona switching, not authentication. Select any dashboard row to open the task detail. The detail
contains only confirmed reading history and linked deterministic rule evidence.

Task workflow endpoints are backend-controlled:

- `GET /api/v1/clinician/tasks/{id}` returns the task detail and actions allowed for the current
  fictional clinician.
- `POST .../{id}/assign` assigns, reassigns, returns to assigned, or explicitly unassigns a task.
- `POST .../{id}/acknowledge` records acknowledgement by the assigned clinician.
- `POST .../{id}/start-review` requires prior acknowledgement and moves the task into review.
- `POST .../{id}/resolve` requires the assigned reviewer and one of the closed demonstration outcome
  codes.
- `POST .../{id}/reopen` requires the assigned clinician and an audit reason.

The locked task path is `open → assigned → in_review → resolved`; the permitted supporting
transitions are enforced server-side. Ownership changes reset acknowledgement. Every real workflow
mutation records an audit event.

While the assigned clinician has a task in review:

- `POST .../{id}/contact-attempts` records a closed contact outcome and optional internal note.
- `POST .../{id}/draft-message` creates a clinician-authored English, Shona, or Ndebele draft.
- `POST .../{id}/approve-message` first approves a named draft and, on a separate request, sends the
  already-approved message to the configured demonstration channel.

The backend rejects direct draft-to-send attempts, wrong-owner actions, messages belonging to another
task, and communication actions outside `in_review`. The clinician task page displays contact history,
message state, and an actor-attributed audit timeline. Simulator `sent` means only that CareSignal
accepted the message; the optional Meta adapter separately records provider `sent`, `delivered`, or
`delivery_failed` webhook status and never equates those states with a patient reading the content.
GPT-5.6 is not used for CS-008 messages; grounded AI drafts are added later in CS-013.

### Patient experience

Open http://localhost:3000/patient for the fictional English structured-entry journey. A reading is
first stored as a pending candidate and appears in clinical history only after **Confirm and save**.
The patient home shows confirmed readings, a neutral follow-up state, and only care-team messages that
were approved and sent to the demonstration channel. It never returns internal task priority or rule
rationale.

The patient-facing API includes `GET /patient/profile`, `GET /patient/follow-up`, and
`GET /patient/messages`. Configure `CARESIGNAL_DEMO_PATIENT_USER_ID` for the server-side demo proxy.
The cross-role English integration test proves the complete patient submission, clinician workflow,
approved response, resolution, and patient retrieval loop without GPT-5.6.

## Validation

```bash
npm run check:web
.venv/bin/ruff check apps/api
.venv/bin/ruff format apps/api --check
.venv/bin/pytest apps/api/tests
```

Failed validation must not be reported as complete. Meaningful work is recorded in `CHANGES.log` under its task ID.
