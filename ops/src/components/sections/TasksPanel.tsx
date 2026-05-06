"use client";

import { useState } from "react";
import { Btn, Pill, Modal, Input, Textarea, Select } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { WorkerTask } from "@/lib/types";

const empty: Partial<WorkerTask> = {
  worker_id: "demo_worker_001", title: "", description: "",
  component_part_code: "", due_date: "", priority: "normal", status: "pending",
};
const PRIORITY_OPTS = [
  { value: "low", label: "low" }, { value: "normal", label: "normal" }, { value: "high", label: "high" },
];
const STATUS_OPTS = [
  { value: "pending", label: "pending" }, { value: "in_progress", label: "in progress" }, { value: "complete", label: "complete" },
];

export function TasksPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<WorkerTask>(
    "worker_tasks", { orderBy: "assigned_at", limit: 50 },
  );
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<WorkerTask | null>(null);
  const [form, setForm] = useState<Partial<WorkerTask>>(empty);
  const [saving, setSaving] = useState(false);
  const [showDone, setShowDone] = useState(false);

  function startCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function startEdit(t: WorkerTask) { setEditing(t); setForm({ ...t }); setOpen(true); }

  async function save() {
    if (!form.title?.trim() || !form.worker_id?.trim()) {
      alert("Title and worker_id are required"); return;
    }
    setSaving(true);
    const completed_at = form.status === "complete"
      && (!editing || editing.status !== "complete")
      ? new Date().toISOString() : editing?.completed_at ?? null;
    const payload = {
      worker_id: form.worker_id?.trim(),
      title: form.title?.trim(),
      description: form.description?.trim() || null,
      component_part_code: form.component_part_code?.trim() || null,
      due_date: form.due_date || null,
      priority: form.priority ?? "normal",
      status: form.status ?? "pending",
      completed_at,
    };
    const { error } = editing
      ? await supabase.from("worker_tasks").update(payload).eq("id", editing.id)
      : await supabase.from("worker_tasks").insert(payload);
    setSaving(false);
    if (error) alert("Save failed: " + error.message); else setOpen(false);
  }
  async function done(t: WorkerTask) {
    const { error } = await supabase.from("worker_tasks")
      .update({ status: "complete", completed_at: new Date().toISOString() }).eq("id", t.id);
    if (error) alert("Failed: " + error.message);
  }
  async function remove(t: WorkerTask) {
    if (!confirm(`Delete "${t.title}"?`)) return;
    const { error } = await supabase.from("worker_tasks").delete().eq("id", t.id);
    if (error) alert("Delete failed: " + error.message);
  }

  const visible = rows.filter((r) => showDone || r.status !== "complete");
  const pending = rows.filter((r) => r.status !== "complete").length;

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold">
          Tasks <span className="text-[var(--warn)] ml-1">{pending > 0 ? `· ${pending} pending` : ""}</span>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-[10.5px] text-[var(--muted)]">
            <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} />
            done
          </label>
          <Btn variant="primary" onClick={startCreate} className="!px-3 !py-1 !text-[11px]">+ NEW</Btn>
        </div>
      </header>
      <div className="flex flex-col gap-1.5 p-3 overflow-y-auto max-h-[420px]">
        {loading ? <div className="text-[12px] text-[var(--muted)]">Loading...</div>
          : visible.length === 0 ? <div className="text-[12px] text-[var(--muted)]">No tasks.</div>
          : visible.slice(0, 30).map((t) => (
            <div key={t.id} className={
              "flex items-center gap-2 p-2.5 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] " +
              (flashIds.has(t.id) ? "flash-in" : "")
            }>
              <Pill tone={t.priority === "high" ? "bad" : t.priority === "low" ? "muted" : "warn"}>
                {t.priority}
              </Pill>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] truncate font-medium">{t.title}</div>
                <div className="text-[10.5px] text-[var(--muted)]">
                  {t.component_part_code ? <span className="font-mono text-[var(--accent)]">{t.component_part_code}</span> : "—"}
                  {" · "}{t.due_date ? `due ${t.due_date}` : "no due"}
                </div>
              </div>
              <Pill tone={t.status === "complete" ? "good" : t.status === "in_progress" ? "accent" : "muted"}>
                {t.status === "in_progress" ? "wip" : t.status}
              </Pill>
              <div className="flex gap-1">
                {t.status !== "complete" && (
                  <Btn variant="primary" onClick={() => done(t)} className="!px-1.5 !py-0.5 !text-[10px]">DONE</Btn>
                )}
                <Btn onClick={() => startEdit(t)} className="!px-1.5 !py-0.5 !text-[10px]">…</Btn>
                <Btn variant="danger" onClick={() => remove(t)} className="!px-1.5 !py-0.5 !text-[10px]">×</Btn>
              </div>
            </div>
          ))}
      </div>

      <Modal open={open} onClose={() => setOpen(false)}
             title={editing ? `EDIT — ${editing.title}` : "NEW TASK"}
             footer={<>
               <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
               <Btn variant="primary" disabled={saving} onClick={save}>
                 {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
               </Btn>
             </>}>
        <Input label="Worker ID *" value={form.worker_id ?? ""} onChange={(e) => setForm({ ...form, worker_id: e.target.value })} />
        <Input label="Title *" value={form.title ?? ""} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <Textarea rows={2} label="Description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <Input label="Component Part Code" value={form.component_part_code ?? ""} onChange={(e) => setForm({ ...form, component_part_code: e.target.value })} />
        <Input type="date" label="Due Date" value={form.due_date ?? ""} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Priority" value={form.priority ?? "normal"} options={PRIORITY_OPTS}
                  onChange={(e) => setForm({ ...form, priority: e.target.value as WorkerTask["priority"] })} />
          <Select label="Status" value={form.status ?? "pending"} options={STATUS_OPTS}
                  onChange={(e) => setForm({ ...form, status: e.target.value as WorkerTask["status"] })} />
        </div>
      </Modal>
    </section>
  );
}
