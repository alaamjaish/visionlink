"use client";

import { useState } from "react";
import { Btn, Pill, Modal, Input, Textarea, Select } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { PartRequest } from "@/lib/types";

const empty: Partial<PartRequest> = {
  worker_id: "demo_worker_001", worker_name: "Alaa",
  part_query: "", matched_part_code: "",
  quantity: 1, urgency: "normal", reason: "", status: "submitted",
};
const URGENCY_OPTS = [
  { value: "normal", label: "normal" }, { value: "urgent", label: "urgent" }, { value: "critical", label: "critical" },
];
const STATUS_OPTS = [
  { value: "submitted", label: "submitted" }, { value: "approved", label: "approved" },
  { value: "shipped", label: "shipped" }, { value: "delivered", label: "delivered" },
];

export function PartsPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<PartRequest>(
    "part_requests", { orderBy: "requested_at", limit: 50 },
  );
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<PartRequest | null>(null);
  const [form, setForm] = useState<Partial<PartRequest>>(empty);
  const [saving, setSaving] = useState(false);

  function startCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function startEdit(p: PartRequest) { setEditing(p); setForm({ ...p }); setOpen(true); }

  async function save() {
    if (!form.part_query?.trim()) { alert("Part query required"); return; }
    setSaving(true);
    const payload = {
      worker_id: form.worker_id?.trim() || null,
      worker_name: form.worker_name?.trim() || null,
      part_query: form.part_query?.trim(),
      matched_part_code: form.matched_part_code?.trim() || null,
      quantity: Number(form.quantity ?? 1) || 1,
      urgency: form.urgency ?? "normal",
      reason: form.reason?.trim() || null,
      status: form.status ?? "submitted",
    };
    const { error } = editing
      ? await supabase.from("part_requests").update(payload).eq("id", editing.id)
      : await supabase.from("part_requests").insert(payload);
    setSaving(false);
    if (error) alert("Save failed: " + error.message); else setOpen(false);
  }
  async function setStatus(p: PartRequest, status: PartRequest["status"]) {
    const { error } = await supabase.from("part_requests").update({ status }).eq("id", p.id);
    if (error) alert("Failed: " + error.message);
  }
  async function remove(p: PartRequest) {
    if (!confirm("Delete this request?")) return;
    const { error } = await supabase.from("part_requests").delete().eq("id", p.id);
    if (error) alert("Delete failed: " + error.message);
  }

  const submitted = rows.filter((r) => r.status === "submitted").length;

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold">
          Parts <span className="text-[var(--warn)] ml-1">{submitted > 0 ? `· ${submitted} new` : ""}</span>
        </div>
        <Btn variant="primary" onClick={startCreate} className="!px-3 !py-1 !text-[11px]">+ NEW</Btn>
      </header>
      <div className="flex flex-col gap-1.5 p-3 overflow-y-auto max-h-[420px]">
        {loading ? <div className="text-[12px] text-[var(--muted)]">Loading...</div>
          : rows.length === 0 ? <div className="text-[12px] text-[var(--muted)]">No part requests.</div>
          : rows.slice(0, 30).map((p) => (
            <div key={p.id} className={
              "flex items-center gap-2 p-2.5 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] " +
              (flashIds.has(p.id) ? "flash-in" : "")
            }>
              <Pill tone={p.urgency === "critical" || p.urgency === "urgent" ? "bad" : "muted"}>
                {p.urgency}
              </Pill>
              <span className="font-mono text-[12px] text-[var(--text)] min-w-[24px] text-center">×{p.quantity}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] truncate font-medium">{p.part_query}</div>
                <div className="text-[10.5px] text-[var(--muted)]">
                  {p.worker_name ?? "—"}
                  {p.matched_part_code && <span className="font-mono text-[var(--accent)] ml-1">· {p.matched_part_code}</span>}
                </div>
              </div>
              <Pill tone={p.status === "delivered" ? "good" : p.status === "shipped" ? "accent" : p.status === "approved" ? "warn" : "muted"}>
                {p.status}
              </Pill>
              <div className="flex gap-1">
                {p.status === "submitted" && (
                  <Btn onClick={() => setStatus(p, "approved")} className="!px-1.5 !py-0.5 !text-[10px]">APPROVE</Btn>
                )}
                {p.status === "approved" && (
                  <Btn onClick={() => setStatus(p, "shipped")} className="!px-1.5 !py-0.5 !text-[10px]">SHIP</Btn>
                )}
                {p.status === "shipped" && (
                  <Btn variant="primary" onClick={() => setStatus(p, "delivered")} className="!px-1.5 !py-0.5 !text-[10px]">DLVR</Btn>
                )}
                <Btn onClick={() => startEdit(p)} className="!px-1.5 !py-0.5 !text-[10px]">…</Btn>
                <Btn variant="danger" onClick={() => remove(p)} className="!px-1.5 !py-0.5 !text-[10px]">×</Btn>
              </div>
            </div>
          ))}
      </div>

      <Modal open={open} onClose={() => setOpen(false)}
             title={editing ? "EDIT REQUEST" : "NEW PART REQUEST"}
             footer={<>
               <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
               <Btn variant="primary" disabled={saving} onClick={save}>
                 {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
               </Btn>
             </>}>
        <Textarea rows={2} label="Part Description *" value={form.part_query ?? ""} onChange={(e) => setForm({ ...form, part_query: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Input type="number" min={1} label="Quantity" value={form.quantity ?? 1} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
          <Select label="Urgency" value={form.urgency ?? "normal"} options={URGENCY_OPTS}
                  onChange={(e) => setForm({ ...form, urgency: e.target.value as PartRequest["urgency"] })} />
        </div>
        <Input label="Matched Part Code" value={form.matched_part_code ?? ""} onChange={(e) => setForm({ ...form, matched_part_code: e.target.value })} />
        <Textarea rows={2} label="Reason" value={form.reason ?? ""} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
        <Select label="Status" value={form.status ?? "submitted"} options={STATUS_OPTS}
                onChange={(e) => setForm({ ...form, status: e.target.value as PartRequest["status"] })} />
      </Modal>
    </section>
  );
}
