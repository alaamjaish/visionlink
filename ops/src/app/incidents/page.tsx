"use client";

import { useState } from "react";
import { Panel, Btn, Pill, Modal, Input, Textarea, Select } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { Incident } from "@/lib/types";

const empty: Partial<Incident> = {
  worker_id: "demo_worker_001",
  worker_name: "Alaa",
  category: "other",
  severity: "medium",
  location: "",
  description: "",
  status: "open",
};

const CATEGORY_OPTS = [
  { value: "safety", label: "safety" },
  { value: "equipment", label: "equipment" },
  { value: "leak", label: "leak" },
  { value: "damage", label: "damage" },
  { value: "other", label: "other" },
];
const SEVERITY_OPTS = [
  { value: "low", label: "low" },
  { value: "medium", label: "medium" },
  { value: "high", label: "high" },
  { value: "critical", label: "critical" },
];
const STATUS_OPTS = [
  { value: "open", label: "open" },
  { value: "acknowledged", label: "acknowledged" },
  { value: "resolved", label: "resolved" },
];

function timeAgo(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
}

export default function IncidentsPage() {
  const { rows, loading, error, flashIds } = useRealtimeRows<Incident>(
    "incidents",
    { orderBy: "reported_at", limit: 200 },
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Incident | null>(null);
  const [form, setForm] = useState<Partial<Incident>>(empty);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState<"all" | "open" | "acknowledged" | "resolved">("all");

  function startCreate() {
    setEditing(null);
    setForm(empty);
    setOpen(true);
  }
  function startEdit(i: Incident) {
    setEditing(i);
    setForm({ ...i });
    setOpen(true);
  }
  async function save() {
    if (!form.description?.trim()) { alert("Description is required"); return; }
    setSaving(true);
    const resolved_at =
      form.status === "resolved" && (!editing || editing.status !== "resolved")
        ? new Date().toISOString()
        : editing?.resolved_at ?? null;
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
    if (error) alert("Save failed: " + error.message);
    else setOpen(false);
  }
  async function setStatus(i: Incident, status: Incident["status"]) {
    const resolved_at = status === "resolved" ? new Date().toISOString() : null;
    const { error } = await supabase
      .from("incidents")
      .update({ status, resolved_at })
      .eq("id", i.id);
    if (error) alert("Failed: " + error.message);
  }
  async function remove(i: Incident) {
    if (!confirm("Delete this incident?")) return;
    const { error } = await supabase.from("incidents").delete().eq("id", i.id);
    if (error) alert("Delete failed: " + error.message);
  }

  const visible = filter === "all" ? rows : rows.filter((r) => r.status === filter);
  const counts = {
    all: rows.length,
    open: rows.filter((r) => r.status === "open").length,
    acknowledged: rows.filter((r) => r.status === "acknowledged").length,
    resolved: rows.filter((r) => r.status === "resolved").length,
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Incidents</h1>
          <p className="text-[var(--muted)] text-sm">
            Live feed. New rows appear here within ~200ms of the agent calling log_incident.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Btn variant="primary" onClick={startCreate}>+ NEW INCIDENT</Btn>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        {(["all", "open", "acknowledged", "resolved"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={
              "px-3 py-1.5 rounded-md text-[12px] tracking-wider uppercase border transition-colors " +
              (filter === k
                ? "bg-[var(--panel)] border-[var(--accent)] text-[var(--text)]"
                : "bg-transparent border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)]")
            }
          >
            {k} <span className="ml-1 text-[10px] opacity-70">{counts[k]}</span>
          </button>
        ))}
      </div>

      <Panel>
        {loading ? (
          <p className="text-[var(--muted)] text-sm">Loading...</p>
        ) : error ? (
          <p className="text-[var(--bad)] text-sm">{error}</p>
        ) : visible.length === 0 ? (
          <p className="text-[var(--muted)] text-sm">No incidents.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {visible.map((i) => (
              <div
                key={i.id}
                className={
                  "flex items-start gap-3 p-3 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] " +
                  (flashIds.has(i.id) ? "flash-in" : "")
                }
              >
                <div className="flex flex-col gap-1 items-start min-w-[88px]">
                  <Pill tone={
                    i.severity === "critical" || i.severity === "high" ? "bad" :
                    i.severity === "medium" ? "warn" : "muted"
                  }>
                    {i.severity ?? "—"}
                  </Pill>
                  <Pill tone="accent">{i.category ?? "—"}</Pill>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium">{i.description}</div>
                  <div className="text-[11px] text-[var(--muted)] mt-1">
                    {i.worker_name ?? "—"} · {i.location ?? "no location"} · {timeAgo(i.reported_at)} ago
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2 min-w-[120px]">
                  <Pill tone={
                    i.status === "open" ? "bad" :
                    i.status === "acknowledged" ? "warn" : "good"
                  }>
                    {i.status}
                  </Pill>
                  <div className="flex gap-1">
                    {i.status === "open" && (
                      <Btn onClick={() => setStatus(i, "acknowledged")} className="!px-2 !py-1 !text-[11px]">ACK</Btn>
                    )}
                    {i.status !== "resolved" && (
                      <Btn variant="primary" onClick={() => setStatus(i, "resolved")} className="!px-2 !py-1 !text-[11px]">
                        RESOLVE
                      </Btn>
                    )}
                    <Btn onClick={() => startEdit(i)} className="!px-2 !py-1 !text-[11px]">EDIT</Btn>
                    <Btn variant="danger" onClick={() => remove(i)} className="!px-2 !py-1 !text-[11px]">DEL</Btn>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "EDIT INCIDENT" : "NEW INCIDENT"}
        footer={
          <>
            <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
            <Btn variant="primary" disabled={saving} onClick={save}>
              {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
            </Btn>
          </>
        }
      >
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
        <Select label="Status" value={form.status ?? "open"} options={STATUS_OPTS}
                onChange={(e) => setForm({ ...form, status: e.target.value as Incident["status"] })} />
      </Modal>
    </div>
  );
}
