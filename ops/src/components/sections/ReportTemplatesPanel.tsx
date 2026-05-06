"use client";

import { useState } from "react";
import { Btn, Pill, Modal, Input, Textarea, Select } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { ReportTemplate } from "@/lib/types";

const empty: Partial<ReportTemplate> = {
  name: "",
  category: "ad_hoc",
  subject: "",
  body_html: "",
  description: "",
};

const CATEGORY_OPTS = [
  { value: "ops_report", label: "ops report" },
  { value: "incident", label: "incident" },
  { value: "task", label: "task" },
  { value: "ad_hoc", label: "ad hoc" },
  { value: "other", label: "other" },
];

export function ReportTemplatesPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<ReportTemplate>(
    "report_templates", { orderBy: "created_at", limit: 50 },
  );
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ReportTemplate | null>(null);
  const [form, setForm] = useState<Partial<ReportTemplate>>(empty);
  const [saving, setSaving] = useState(false);

  function startCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function startEdit(t: ReportTemplate) { setEditing(t); setForm({ ...t }); setOpen(true); }

  async function save() {
    if (!form.name?.trim() || !form.subject?.trim() || !form.body_html?.trim()) {
      alert("Name, subject, and body are required"); return;
    }
    setSaving(true);
    const payload = {
      name: form.name?.trim(),
      category: form.category ?? "ad_hoc",
      subject: form.subject?.trim(),
      body_html: form.body_html?.trim(),
      description: form.description?.trim() || null,
    };
    const { error } = editing
      ? await supabase.from("report_templates").update(payload).eq("id", editing.id)
      : await supabase.from("report_templates").insert(payload);
    setSaving(false);
    if (error) alert("Save failed: " + error.message); else setOpen(false);
  }
  async function remove(t: ReportTemplate) {
    if (!confirm(`Delete template "${t.name}"?`)) return;
    const { error } = await supabase.from("report_templates").delete().eq("id", t.id);
    if (error) alert("Delete failed: " + error.message);
  }

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold">
          Report Templates <span className="text-[var(--accent)] ml-1">· {rows.length}</span>
        </div>
        <Btn variant="primary" onClick={startCreate} className="!px-3 !py-1 !text-[11px]">+ NEW</Btn>
      </header>
      <div className="flex flex-col gap-1.5 p-3 overflow-y-auto max-h-[420px]">
        {loading ? <div className="text-[12px] text-[var(--muted)]">Loading...</div>
          : rows.length === 0 ? <div className="text-[12px] text-[var(--muted)]">No templates yet.</div>
          : rows.map((t) => (
            <div key={t.id} className={
              "flex items-center gap-2 p-2.5 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] " +
              (flashIds.has(t.id) ? "flash-in" : "")
            }>
              <Pill tone="accent">{t.category ?? "—"}</Pill>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] font-medium truncate">{t.name}</div>
                <div className="text-[10.5px] text-[var(--muted)] truncate">{t.subject}</div>
              </div>
              <div className="flex gap-1">
                <Btn onClick={() => startEdit(t)} className="!px-1.5 !py-0.5 !text-[10px]">…</Btn>
                <Btn variant="danger" onClick={() => remove(t)} className="!px-1.5 !py-0.5 !text-[10px]">×</Btn>
              </div>
            </div>
          ))}
      </div>

      <Modal open={open} onClose={() => setOpen(false)}
             title={editing ? `EDIT — ${editing.name}` : "NEW REPORT TEMPLATE"}
             footer={<>
               <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
               <Btn variant="primary" disabled={saving} onClick={save}>
                 {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
               </Btn>
             </>}>
        <Input label="Template Name *" value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Select label="Category" value={form.category ?? "ad_hoc"} options={CATEGORY_OPTS}
                onChange={(e) => setForm({ ...form, category: e.target.value })} />
        <Input label="Email Subject *" value={form.subject ?? ""}
               placeholder="Daily Operations Report — {{date}}"
               onChange={(e) => setForm({ ...form, subject: e.target.value })} />
        <Textarea rows={10} label="Body (HTML, with {{vars}}) *"
                  value={form.body_html ?? ""}
                  placeholder="<p>Hi {{recipient_name}}, ...</p>"
                  onChange={(e) => setForm({ ...form, body_html: e.target.value })} />
        <Textarea rows={2} label="Description (internal note)" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <div className="text-[11px] text-[var(--muted)] leading-relaxed">
          <b>Available variables:</b> <code>{"{{date}}"}</code>, <code>{"{{datetime}}"}</code>,{" "}
          <code>{"{{worker_name}}"}</code>, <code>{"{{recipient_name}}"}</code>,{" "}
          <code>{"{{recipient_role}}"}</code>, <code>{"{{custom_message}}"}</code>,{" "}
          <code>{"{{recent_incidents}}"}</code>, <code>{"{{recent_tasks}}"}</code>,{" "}
          <code>{"{{recent_parts}}"}</code> (last three are auto-fetched live from Supabase).
        </div>
      </Modal>
    </section>
  );
}
