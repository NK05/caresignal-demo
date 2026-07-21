export type TaskPriority = "routine" | "watch" | "needs_review" | "urgent_review";
export type TaskStatus = "open" | "assigned" | "in_review" | "resolved";
export type Language = "en" | "sn" | "nd" | "mixed" | "unknown";
export type Channel = "app" | "whatsapp_simulator" | "whatsapp_sandbox";
export type MedicationStatus = "yes" | "no" | "unknown" | "prefer_not_to_say";

export interface ClinicianOwner {
  clinician_id: string;
  display_name: string;
  display_role: string;
}

export interface DashboardReading {
  reading_id: string;
  systolic: number;
  diastolic: number;
  measured_at: string;
  medication_taken: MedicationStatus;
}

export interface ClinicianTask {
  task_id: string;
  patient_id: string;
  patient_synthetic_identifier: string;
  patient_display_name: string;
  preferred_language: Language;
  preferred_channel: Channel;
  priority: TaskPriority;
  status: TaskStatus;
  flag_title: string;
  flag_reason: string;
  rule_version: string;
  latest_reading: DashboardReading;
  medication_adherence_signal: boolean;
  assigned_owner: ClinicianOwner | null;
  evidence_count: number;
  opened_at: string;
  due_at: string | null;
  task_age_minutes: number;
  overdue: boolean;
  unacknowledged: boolean;
}

export interface ClinicianDashboardData {
  generated_at: string;
  synthetic_data: true;
  summary: {
    unassigned: number;
    awaiting_acknowledgement: number;
    in_review: number;
    overdue: number;
    resolved_today: number;
  };
  tasks: ClinicianTask[];
  available_owners: ClinicianOwner[];
}

export interface ClinicianTaskReadingDetail {
  reading_id: string;
  systolic: number;
  diastolic: number;
  measured_at: string;
  confirmed_at: string;
  medication_taken: MedicationStatus;
  missed_medication_reason_code: string | null;
  context_codes: string[];
  note: string | null;
}

export interface ClinicianTaskEvidenceDetail {
  rule_evaluation_id: string;
  reading_id: string;
  rule_id: string;
  rule_version: string;
  priority: TaskPriority;
  title: string;
  reason: string;
  source_reference: string;
  evaluated_at: string;
  observed_values: Array<Record<string, unknown>>;
}

export interface ClinicianTaskAllowedActions {
  can_assign: boolean;
  can_unassign: boolean;
  can_acknowledge: boolean;
  can_start_review: boolean;
  can_return_to_assigned: boolean;
  can_resolve: boolean;
  can_reopen: boolean;
  can_record_contact: boolean;
  can_draft_message: boolean;
}

export interface ClinicianContactAttempt {
  contact_attempt_id: string;
  clinician: ClinicianOwner;
  channel: Channel;
  outcome_code: string;
  note: string | null;
  attempted_at: string;
}

export interface ClinicianPatientMessage {
  message_id: string;
  channel: Channel;
  language: Language;
  content: string;
  generation_type: "fixed_template" | "ai_draft" | "clinician_authored";
  approval_status: "draft" | "approved" | "sent" | "rejected";
  approved_by: string | null;
  approved_at: string | null;
  sent_at: string | null;
  delivery_status: "not_sent" | "sent" | "delivered" | "delivery_failed";
  created_at: string;
}

export interface ClinicianAuditEvent {
  audit_event_id: string;
  actor_display_name: string;
  event_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ClinicianTaskDetailData {
  generated_at: string;
  synthetic_data: true;
  task: ClinicianTask;
  acknowledged_at: string | null;
  resolved_at: string | null;
  outcome_code: string | null;
  outcome_note: string | null;
  reopened_count: number;
  readings: ClinicianTaskReadingDetail[];
  evidence: ClinicianTaskEvidenceDetail[];
  available_owners: ClinicianOwner[];
  current_clinician: ClinicianOwner;
  allowed_actions: ClinicianTaskAllowedActions;
  contact_attempts: ClinicianContactAttempt[];
  messages: ClinicianPatientMessage[];
  audit_events: ClinicianAuditEvent[];
}
