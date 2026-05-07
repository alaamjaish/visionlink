// Hand-written DB row shapes — match the SQL schemas in Supabase.

export type Component = {
  id: string;
  name: string;
  part_code: string | null;
  description: string | null;
  torque_spec: string | null;
  maintenance_interval: string | null;
  safety_notes: string | null;
  image_url: string | null;
  created_at: string;
};

export type WorkerTask = {
  id: string;
  worker_id: string;
  title: string;
  description: string | null;
  component_part_code: string | null;
  due_date: string | null;
  priority: "low" | "normal" | "high";
  status: "pending" | "in_progress" | "complete";
  assigned_at: string;
  completed_at: string | null;
};

export type Incident = {
  id: string;
  worker_id: string | null;
  worker_name: string | null;
  category: "safety" | "equipment" | "leak" | "damage" | "other" | null;
  severity: "low" | "medium" | "high" | "critical" | null;
  location: string | null;
  description: string;
  reported_at: string;
  resolved_at: string | null;
  status: "open" | "acknowledged" | "resolved";
};

export type Manager = {
  id: string;
  name: string;
  email: string;
  role: string | null;
  notes: string | null;
  created_at: string;
};

export type ReportTemplate = {
  id: string;
  name: string;
  category: string | null;
  subject: string;
  body_html: string;
  description: string | null;
  created_at: string;
};

export type SentReport = {
  id: string;
  worker_id: string | null;
  worker_name: string | null;
  recipient_name: string | null;
  recipient_email: string | null;
  recipient_role: string | null;
  template_name: string | null;
  subject: string | null;
  body_html: string | null;
  custom_message: string | null;
  status: "sent" | "failed";
  error: string | null;
  provider: "resend" | "gmail_smtp" | null;
  sent_at: string;
};

export type PartRequest = {
  id: string;
  worker_id: string | null;
  worker_name: string | null;
  part_query: string;
  matched_part_code: string | null;
  quantity: number;
  urgency: "normal" | "urgent" | "critical";
  reason: string | null;
  requested_at: string;
  status: "submitted" | "approved" | "shipped" | "delivered";
};

// ---------- 6-button system + SOS panic mode ----------

export type WearableSettings = {
  id: "current";
  b4_provider: "gemini" | "openai";
  b5_provider: "gemini" | "openai";
  b5_vision_mode: "snap_on_press" | "gemini_video" | "auto_snap_4s";
  sos_photo_interval_s: number;
  sos_max_duration_s: number;
  sos_alert_recipient_role: string;
  sos_provider: "gemini" | "openai";
  worker_id: string;
  worker_name: string;
  updated_at: string;
};

export type Session = {
  id: string;
  worker_id: string;
  worker_name: string | null;
  label: string | null;
  started_at: string;
  ended_at: string | null;
  status: "open" | "closed";
};

export type SessionAsset = {
  id: string;
  session_id: string | null;
  worker_id: string;
  kind: "photo" | "video" | "voice_note";
  storage_path: string;
  captured_at: string;
  duration_s: number | null;
  notes: string | null;
};

export type SosEvent = {
  id: string;
  worker_id: string;
  worker_name: string | null;
  triggered_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolved: boolean;
  reason: string | null;
  live_transcript: string;
  frames_sent: number;
  email_sent: boolean;
  notes: string | null;
};
