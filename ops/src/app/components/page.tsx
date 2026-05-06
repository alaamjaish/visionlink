"use client";

import { useState } from "react";
import { Panel, Btn, Pill, Modal, Input, Textarea } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { Component } from "@/lib/types";

type FormState = Partial<Component>;

const empty: FormState = {
  name: "",
  part_code: "",
  description: "",
  torque_spec: "",
  maintenance_interval: "",
  safety_notes: "",
};

export default function ComponentsPage() {
  const { rows, loading, error, flashIds } = useRealtimeRows<Component>(
    "components",
    { orderBy: "created_at", limit: 200 },
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Component | null>(null);
  const [form, setForm] = useState<FormState>(empty);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState("");

  function startCreate() {
    setEditing(null);
    setForm(empty);
    setOpen(true);
  }
  function startEdit(c: Component) {
    setEditing(c);
    setForm({ ...c });
    setOpen(true);
  }
  async function save() {
    if (!form.name?.trim()) { alert("Name is required"); return; }
    setSaving(true);
    const payload: FormState = {
      name: form.name?.trim(),
      part_code: form.part_code?.trim() || null,
      description: form.description?.trim() || null,
      torque_spec: form.torque_spec?.trim() || null,
      maintenance_interval: form.maintenance_interval?.trim() || null,
      safety_notes: form.safety_notes?.trim() || null,
    };
    const { error } = editing
      ? await supabase.from("components").update(payload).eq("id", editing.id)
      : await supabase.from("components").insert(payload);
    setSaving(false);
    if (error) alert("Save failed: " + error.message);
    else setOpen(false);
  }
  async function remove(c: Component) {
    if (!confirm(`Delete "${c.name}"?`)) return;
    const { error } = await supabase.from("components").delete().eq("id", c.id);
    if (error) alert("Delete failed: " + error.message);
  }

  const visible = rows.filter(
    (r) =>
      !filter ||
      r.name?.toLowerCase().includes(filter.toLowerCase()) ||
      r.part_code?.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Components</h1>
          <p className="text-[var(--muted)] text-sm">Factory parts catalog. Live-synced with the Pi.</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            placeholder="search name or part code..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-[var(--panel-2)] border border-[var(--border)] rounded-md px-3 py-2 text-[13px] w-64 text-[var(--text)]"
          />
          <Btn variant="primary" onClick={startCreate}>+ NEW COMPONENT</Btn>
        </div>
      </div>

      <Panel>
        {loading ? (
          <p className="text-[var(--muted)] text-sm">Loading...</p>
        ) : error ? (
          <p className="text-[var(--bad)] text-sm">{error}</p>
        ) : visible.length === 0 ? (
          <p className="text-[var(--muted)] text-sm">No components{filter ? " match that filter" : " yet"}.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] border-collapse">
              <thead>
                <tr className="text-left text-[10.5px] uppercase tracking-[0.12em] text-[var(--muted)]">
                  <th className="py-2 px-3">Part Code</th>
                  <th className="py-2 px-3">Name</th>
                  <th className="py-2 px-3">Torque</th>
                  <th className="py-2 px-3">Maintenance</th>
                  <th className="py-2 px-3 w-24"></th>
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <tr
                    key={c.id}
                    className={
                      "border-t border-[var(--border)] hover:bg-[var(--panel-2)] " +
                      (flashIds.has(c.id) ? "flash-in" : "")
                    }
                  >
                    <td className="py-2 px-3 font-mono text-[var(--accent)]">{c.part_code ?? "—"}</td>
                    <td className="py-2 px-3 font-semibold">{c.name}</td>
                    <td className="py-2 px-3 text-[var(--muted)] truncate max-w-[200px]">{c.torque_spec ?? "—"}</td>
                    <td className="py-2 px-3 text-[var(--muted)] truncate max-w-[260px]">{c.maintenance_interval ?? "—"}</td>
                    <td className="py-2 px-3">
                      <div className="flex gap-1 justify-end">
                        <Btn onClick={() => startEdit(c)} className="!px-2 !py-1 !text-[11px]">EDIT</Btn>
                        <Btn variant="danger" onClick={() => remove(c)} className="!px-2 !py-1 !text-[11px]">DEL</Btn>
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
        title={editing ? `EDIT — ${editing.name}` : "NEW COMPONENT"}
        footer={
          <>
            <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
            <Btn variant="primary" disabled={saving} onClick={save}>
              {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
            </Btn>
          </>
        }
      >
        <Input label="Name *" value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Input label="Part Code" value={form.part_code ?? ""} onChange={(e) => setForm({ ...form, part_code: e.target.value })} />
        <Textarea rows={2} label="Description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <Input label="Torque Spec" value={form.torque_spec ?? ""} onChange={(e) => setForm({ ...form, torque_spec: e.target.value })} />
        <Input label="Maintenance Interval" value={form.maintenance_interval ?? ""} onChange={(e) => setForm({ ...form, maintenance_interval: e.target.value })} />
        <Textarea rows={2} label="Safety Notes" value={form.safety_notes ?? ""} onChange={(e) => setForm({ ...form, safety_notes: e.target.value })} />
      </Modal>
    </div>
  );
}
