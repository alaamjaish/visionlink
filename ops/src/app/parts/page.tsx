"use client";

import { useState } from "react";
import { Panel, Btn, Pill, Modal, Input, Textarea, Select } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { PartRequest } from "@/lib/types";

const empty: Partial<PartRequest> = {
  worker_id: "demo_worker_001",
  worker_name: "Alaa",
  part_query: "",
  matched_part_code: "",
  quantity: 1,
  urgency: "normal",
  reason: "",
  status: "submitted",
};

const URGENCY_OPTS = [
  { value: "normal", label: "normal" },
  { value: "urgent", label: "urgent" },
  { value: "critical", label: "critical" },
];
const STATUS_OPTS = [
  { value: "submitted", label: "submitted" },
  { value: "approved", label: "approved" },
  { value: "shipped", label: "shipped" },
  { value: "delivered", label: "delivered" },
];

export default function PartsPage() {
  const { rows, loading, error, flashIds } = useRealtimeRows<PartRequest>(
    "part_requests",
    { orderBy: "requested_at", limit: 200 },
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<PartRequest | null>(null);
  const [form, setForm] = useState<Partial<PartRequest>>(empty);
  const [saving, setSaving] = useState(false);

  function startCreate() {
    setEditing(null);
    setForm(empty);
    setOpen(true);
  }
  function startEdit(p: PartRequest) {
    setEditing(p);
    setForm({ ...p });
    setOpen(true);
  }
  async function save() {
    if (!form.part_query?.trim()) { alert("Part query is required"); return; }
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
    if (error) alert("Save failed: " + error.message);
    else setOpen(false);
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Part Requests</h1>
          <p className="text-[var(--muted)] text-sm">
            Worker-submitted parts orders. The agent calls request_part to insert here.
          </p>
        </div>
        <Btn variant="primary" onClick={startCreate}>+ NEW REQUEST</Btn>
      </div>

      <Panel>
        {loading ? (
          <p className="text-[var(--muted)] text-sm">Loading...</p>
        ) : error ? (
          <p className="text-[var(--bad)] text-sm">{error}</p>
        ) : rows.length === 0 ? (
          <p className="text-[var(--muted)] text-sm">No part requests yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] border-collapse">
              <thead>
                <tr className="text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--muted)]">
                  <th className="py-2 px-3 w-24">Urgency</th>
                  <th className="py-2 px-3 w-12">Qty</th>
                  <th className="py-2 px-3">Request</th>
                  <th className="py-2 px-3">Matched</th>
                  <th className="py-2 px-3">Worker</th>
                  <th className="py-2 px-3 w-32">Status</th>
                  <th className="py-2 px-3 w-44"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr
                    key={p.id}
                    className={
                      "border-t border-[var(--border)] hover:bg-[var(--panel-2)] " +
                      (flashIds.has(p.id) ? "flash-in" : "")
                    }
                  >
                    <td className="py-2 px-3">
                      <Pill tone={p.urgency === "critical" || p.urgency === "urgent" ? "bad" : "muted"}>
                        {p.urgency}
                      </Pill>
                    </td>
                    <td className="py-2 px-3 font-mono text-center">{p.quantity}</td>
                    <td className="py-2 px-3">
                      <div className="font-medium">{p.part_query}</div>
                      {p.reason && <div className="text-[11px] text-[var(--muted)] mt-0.5">{p.reason}</div>}
                    </td>
                    <td className="py-2 px-3 font-mono text-[var(--accent)]">{p.matched_part_code ?? "—"}</td>
                    <td className="py-2 px-3 text-[var(--muted)]">{p.worker_name ?? p.worker_id ?? "—"}</td>
                    <td className="py-2 px-3">
                      <Pill tone={
                        p.status === "delivered" ? "good" :
                        p.status === "shipped" ? "accent" :
                        p.status === "approved" ? "warn" : "muted"
                      }>
                        {p.status}
                      </Pill>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex gap-1 justify-end">
                        {p.status === "submitted" && (
                          <Btn onClick={() => setStatus(p, "approved")} className="!px-2 !py-1 !text-[11px]">APPROVE</Btn>
                        )}
                        {p.status === "approved" && (
                          <Btn onClick={() => setStatus(p, "shipped")} className="!px-2 !py-1 !text-[11px]">SHIP</Btn>
                        )}
                        {p.status === "shipped" && (
                          <Btn variant="primary" onClick={() => setStatus(p, "delivered")} className="!px-2 !py-1 !text-[11px]">
                            DELIVERED
                          </Btn>
                        )}
                        <Btn onClick={() => startEdit(p)} className="!px-2 !py-1 !text-[11px]">EDIT</Btn>
                        <Btn variant="danger" onClick={() => remove(p)} className="!px-2 !py-1 !text-[11px]">DEL</Btn>
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
        title={editing ? "EDIT REQUEST" : "NEW PART REQUEST"}
        footer={
          <>
            <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
            <Btn variant="primary" disabled={saving} onClick={save}>
              {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
            </Btn>
          </>
        }
      >
        <Textarea rows={2} label="Part Description *" value={form.part_query ?? ""} onChange={(e) => setForm({ ...form, part_query: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Input type="number" min={1} label="Quantity" value={form.quantity ?? 1} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
          <Select label="Urgency" value={form.urgency ?? "normal"} options={URGENCY_OPTS}
                  onChange={(e) => setForm({ ...form, urgency: e.target.value as PartRequest["urgency"] })} />
        </div>
        <Input label="Matched Part Code" value={form.matched_part_code ?? ""} onChange={(e) => setForm({ ...form, matched_part_code: e.target.value })} />
        <Textarea rows={2} label="Reason" value={form.reason ?? ""} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Worker ID" value={form.worker_id ?? ""} onChange={(e) => setForm({ ...form, worker_id: e.target.value })} />
          <Input label="Worker Name" value={form.worker_name ?? ""} onChange={(e) => setForm({ ...form, worker_name: e.target.value })} />
        </div>
        <Select label="Status" value={form.status ?? "submitted"} options={STATUS_OPTS}
                onChange={(e) => setForm({ ...form, status: e.target.value as PartRequest["status"] })} />
      </Modal>
    </div>
  );
}
