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
