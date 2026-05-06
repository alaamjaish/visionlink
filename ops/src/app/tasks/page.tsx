"use client";

import { useState } from "react";
import { Panel, Btn, Pill, Modal, Input, Textarea, Select } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { WorkerTask } from "@/lib/types";

const empty: Partial<WorkerTask> = {
  worker_id: "demo_worker_001",
  title: "",
  description: "",
  component_part_code: "",
  due_date: "",
  priority: "normal",
  status: "pending",
};

const PRIORITY_OPTS = [
  { value: "low", label: "low" },
  { value: "normal", label: "normal" },
  { value: "high", label: "high" },
];
const STATUS_OPTS = [
  { value: "pending", label: "pending" },
  { value: "in_progress", label: "in progress" },
  { value: "complete", label: "complete" },
];

export default function TasksPage() {
  const { rows, loading, error, flashIds } = useRealtimeRows<WorkerTask>(
    "worker_tasks",
    { orderBy: "assigned_at", limit: 200 },
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<WorkerTask | null>(null);
  const [form, setForm] = useState<Partial<WorkerTask>>(empty);
  const [saving, setSaving] = useState(false);
  const [showComplete, setShowComplete] = useState(false);

  function startCreate() {
    setEditing(null);
    setForm(empty);
    setOpen(true);
  }
  function startEdit(t: WorkerTask) {
    setEditing(t);
    setForm({ ...t });
    setOpen(true);
  }
  async function save() {
    if (!form.title?.trim() || !form.worker_id?.trim()) {
      alert("Title and worker_id are required"); return;
    }
    setSaving(true);
    const completed_at =
      form.status === "complete" && (!editing || editing.status !== "complete")
        ? new Date().toISOString()
        : editing?.completed_at ?? null;
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
    if (error) alert("Save failed: " + error.message);
    else setOpen(false);
  }
  async function remove(t: WorkerTask) {
    if (!confirm(`Delete task "${t.title}"?`)) return;
    const { error } = await supabase.from("worker_tasks").delete().eq("id", t.id);
    if (error) alert("Delete failed: " + error.message);
  }
  async function quickComplete(t: WorkerTask) {
    const { error } = await supabase
      .from("worker_tasks")
      .update({ status: "complete", completed_at: new Date().toISOString() })
      .eq("id", t.id);
    if (error) alert("Failed: " + error.message);
  }

  const visible = rows.filter((r) => showComplete || r.status !== "complete");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Tasks</h1>
          <p className="text-[var(--muted)] text-sm">Worker assignments. The agent reads these via get_my_assignments.</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
            <input type="checkbox" checked={showComplete} onChange={(e) => setShowComplete(e.target.checked)} />
            show completed
          </label>
          <Btn variant="primary" onClick={startCreate}>+ NEW TASK</Btn>
        </div>
      </div>

      <Panel>
        {loading ? (
          <p className="text-[var(--muted)] text-sm">Loading...</p>
        ) : error ? (
          <p className="text-[var(--bad)] text-sm">{error}</p>
        ) : visible.length === 0 ? (
          <p className="text-[var(--muted)] text-sm">No tasks.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] border-collapse">
              <thead>
                <tr className="text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--muted)]">
                  <th className="py-2 px-3 w-24">Priority</th>
                  <th className="py-2 px-3">Title</th>
                  <th className="py-2 px-3">Worker</th>
                  <th className="py-2 px-3">Part Code</th>
                  <th className="py-2 px-3 w-28">Due</th>
                  <th className="py-2 px-3 w-28">Status</th>
                  <th className="py-2 px-3 w-40"></th>
                </tr>
              </thead>
              <tbody>
                {visible.map((t) => (
                  <tr
                    key={t.id}
                    className={
                      "border-t border-[var(--border)] hover:bg-[var(--panel-2)] " +
                      (flashIds.has(t.id) ? "flash-in" : "")
                    }
                  >
                    <td className="py-2 px-3">
                      <Pill tone={t.priority === "high" ? "bad" : t.priority === "low" ? "muted" : "warn"}>
                        {t.priority}
                      </Pill>
                    </td>
                    <td className="py-2 px-3 font-semibold">{t.title}</td>
                    <td className="py-2 px-3 text-[var(--muted)]">{t.worker_id}</td>
                    <td className="py-2 px-3 font-mono text-[var(--accent)]">{t.component_part_code ?? "—"}</td>
                    <td className="py-2 px-3 text-[var(--muted)]">{t.due_date ?? "—"}</td>
                    <td className="py-2 px-3">
                      <Pill tone={
                        t.status === "complete" ? "good" :
                        t.status === "in_progress" ? "accent" : "muted"
                      }>
                        {t.status}
                      </Pill>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex gap-1 justify-end">
                        {t.status !== "complete" && (
                          <Btn variant="primary" onClick={() => quickComplete(t)} className="!px-2 !py-1 !text-[11px]">
                            DONE
                          </Btn>
                        )}
                        <Btn onClick={() => startEdit(t)} className="!px-2 !py-1 !text-[11px]">EDIT</Btn>
                        <Btn variant="danger" onClick={() => remove(t)} className="!px-2 !py-1 !text-[11px]">DEL</Btn>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? `EDIT — ${editing.title}` : "NEW TASK"}
        footer={
          <>
            <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
            <Btn variant="primary" disabled={saving} onClick={save}>
              {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
            </Btn>
          </>
        }
      >
        <Input label="Worker ID *" value={form.worker_id ?? ""} onChange={(e) => setForm({ ...form, worker_id: e.target.value })} />
        <Input label="Title *" value={form.title ?? ""} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <Textarea rows={2} label="Description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <Input label="Component Part Code" value={form.component_part_code ?? ""} onChange={(e) => setForm({ ...form, component_part_code: e.target.value })} />
        <Input type="date" label="Due Date" value={form.due_date ?? ""} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
        <Select label="Priority" value={form.priority ?? "normal"} options={PRIORITY_OPTS}
                onChange={(e) => setForm({ ...form, priority: e.target.value as WorkerTask["priority"] })} />
        <Select label="Status" value={form.status ?? "pending"} options={STATUS_OPTS}
                onChange={(e) => setForm({ ...form, status: e.target.value as WorkerTask["status"] })} />
      </Modal>
    </div>
  );
}
