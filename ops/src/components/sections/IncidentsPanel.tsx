"use client";

import { useState } from "react";
import { Btn, Pill, Modal, Input, Textarea, Select } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { Incident } from "@/lib/types";

const empty: Partial<Incident> = {
  worker_id: "demo_worker_001", worker_name: "Alaa",
  category: "other", severity: "medium",
  location: "", description: "", status: "open",
};
const CATEGORY_OPTS = [
  { value: "safety", label: "safety" }, { value: "equipment", label: "equipment" },
  { value: "leak", label: "leak" }, { value: "damage", label: "damage" },
  { value: "other", label: "other" },
];
const SEVERITY_OPTS = [
  { value: "low", label: "low" }, { value: "medium", label: "medium" },
  { value: "high", label: "high" }, { value: "critical", label: "critical" },
];

function timeAgo(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

export function IncidentsPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<Incident>(
    "incidents", { orderBy: "reported_at", limit: 50 },
  );
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Incident | null>(null);
  const [form, setForm] = useState<Partial<Incident>>(empty);
  const [saving, setSaving] = useState(false);

  function startCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function startEdit(i: Incident) { setEditing(i); setForm({ ...i }); setOpen(true); }

  async function save() {
    if (!form.description?.trim()) { alert("Description required"); return; }
    setSaving(true);
    const resolved_at = form.status === "resolved"
      && (!editing || editing.status !== "resolved")
      ? new Date().toISOString() : editing?.resolved_at ?? null;
    const payload = {
      worker_id: form.worker_id?.trim() || null,
      worker_name: form.worker_name?.trim() || null,
      category: form.category ?? "other",
      severity: form.severity ?? "medium",
      location: form.location?.trim() || null,
      description: form.description?.trim(),
      status: form.status ?? "open",
      resolved_at,
    };
    const { error } = editing
      ? await supabase.from("incidents").update(payload).eq("id", editing.id)
      : await supabase.from("incidents").insert(payload);
    setSaving(false);
    if (error) alert("Save failed: " + error.message); else setOpen(false);
  }
  async function setStatus(i: Incident, status: Incident["status"]) {
    const resolved_at = status === "resolved" ? new Date().toISOString() : null;
    const { error } = await supabase.from("incidents")
      .update({ status, resolved_at }).eq("id", i.id);
    if (error) alert("Failed: " + error.message);
  }
  async function remove(i: Incident) {
    if (!confirm("Delete this incident?")) return;
    const { error } = await supabase.from("incidents").delete().eq("id", i.id);
    if (error) alert("Delete failed: " + error.message);
  }

  const open_ = rows.filter((r) => r.status === "open").length;

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div>
          <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold">
            Incidents <span className="text-[var(--bad)] ml-1">{open_ > 0 ? `· ${open_} open` : ""}</span>
          </div>
        </div>
        <Btn variant="primary" onClick={startCreate} className="!px-3 !py-1 !text-[11px]">+ NEW</Btn>
      </header>
      <div className="flex flex-col gap-1.5 p-3 overflow-y-auto max-h-[420px]">
        {loading ? <div className="text-[12px] text-[var(--muted)]">Loading...</div>
          : rows.length === 0 ? <div className="text-[12px] text-[var(--muted)]">No incidents.</div>
          : rows.slice(0, 30).map((i) => (
            <div key={i.id} className={
              "flex items-start gap-2 p-2.5 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] " +
              (flashIds.has(i.id) ? "flash-in" : "")
            }>
              <div className="flex flex-col gap-1 min-w-[68px]">
                <Pill tone={i.severity === "critical" || i.severity === "high" ? "bad" : i.severity === "medium" ? "warn" : "muted"}>
                  {i.severity ?? "—"}
                </Pill>
                <span className="text-[10px] text-[var(--muted)] uppercase tracking-wider">{i.category ?? "—"}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] leading-snug">{i.description}</div>
                <div className="text-[10.5px] text-[var(--muted)] mt-1">
                  {i.worker_name ?? "—"} · {i.location ?? "no location"} · {timeAgo(i.reported_at)} ago
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Pill tone={i.status === "open" ? "bad" : i.status === "acknowledged" ? "warn" : "good"}>
                  {i.status}
                </Pill>
                <div className="flex gap-1">
                  {i.status === "open" && (
                    <Btn onClick={() => setStatus(i, "acknowledged")} className="!px-1.5 !py-0.5 !text-[10px]">ACK</Btn>
                  )}
                  {i.status !== "resolved" && (
                    <Btn variant="primary" onClick={() => setStatus(i, "resolved")} className="!px-1.5 !py-0.5 !text-[10px]">RES</Btn>
                  )}
                  <Btn onClick={() => startEdit(i)} className="!px-1.5 !py-0.5 !text-[10px]">…</Btn>
                  <Btn variant="danger" onClick={() => remove(i)} className="!px-1.5 !py-0.5 !text-[10px]">×</Btn>
                </div>
              </div>
            </div>
          ))}
      </div>

      <Modal open={open} onClose={() => setOpen(false)}
             title={editing ? "EDIT INCIDENT" : "NEW INCIDENT"}
             footer={<>
               <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
               <Btn variant="primary" disabled={saving} onClick={save}>
                 {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
               </Btn>
             </>}>
        <Textarea rows={3} label="Description *" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Category" value={form.category ?? "other"} options={CATEGORY_OPTS}
                  onChange={(e) => setForm({ ...form, category: e.target.value as Incident["category"] })} />
          <Select label="Severity" value={form.severity ?? "medium"} options={SEVERITY_OPTS}
                  onChange={(e) => setForm({ ...form, severity: e.target.value as Incident["severity"] })} />
        </div>
        <Input label="Location" value={form.location ?? ""} onChange={(e) => setForm({ ...form, location: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Worker ID" value={form.worker_id ?? ""} onChange={(e) => setForm({ ...form, worker_id: e.target.value })} />
          <Input label="Worker Name" value={form.worker_name ?? ""} onChange={(e) => setForm({ ...form, worker_name: e.target.value })} />
        </div>
      </Modal>
    </section>
  );
}
