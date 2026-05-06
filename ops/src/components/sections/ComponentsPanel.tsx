"use client";

import { useState } from "react";
import { Btn, Modal, Input, Textarea } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { Component } from "@/lib/types";

const empty: Partial<Component> = {
  name: "", part_code: "", description: "",
  torque_spec: "", maintenance_interval: "", safety_notes: "",
};

export function ComponentsPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<Component>(
    "components", { orderBy: "created_at", limit: 100 },
  );
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Component | null>(null);
  const [form, setForm] = useState<Partial<Component>>(empty);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState("");

  function startCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function startEdit(c: Component) { setEditing(c); setForm({ ...c }); setOpen(true); }

  async function save() {
    if (!form.name?.trim()) { alert("Name required"); return; }
    setSaving(true);
    const payload = {
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
    if (error) alert("Save failed: " + error.message); else setOpen(false);
  }
  async function remove(c: Component) {
    if (!confirm(`Delete "${c.name}"?`)) return;
    const { error } = await supabase.from("components").delete().eq("id", c.id);
    if (error) alert("Delete failed: " + error.message);
  }

  const visible = rows.filter((r) =>
    !filter ||
    r.name?.toLowerCase().includes(filter.toLowerCase()) ||
    r.part_code?.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] gap-2">
        <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold whitespace-nowrap">
          Components <span className="text-[var(--accent)] ml-1">· {rows.length}</span>
        </div>
        <input
          placeholder="search..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-[var(--panel-2)] border border-[var(--border)] rounded px-2 py-1 text-[11px] flex-1 min-w-0 max-w-[180px] text-[var(--text)]"
        />
        <Btn variant="primary" onClick={startCreate} className="!px-3 !py-1 !text-[11px]">+ NEW</Btn>
      </header>
      <div className="flex flex-col gap-1.5 p-3 overflow-y-auto max-h-[420px]">
        {loading ? <div className="text-[12px] text-[var(--muted)]">Loading...</div>
          : visible.length === 0 ? <div className="text-[12px] text-[var(--muted)]">{filter ? "No matches." : "No components."}</div>
          : visible.slice(0, 50).map((c) => (
            <div key={c.id} className={
              "flex items-center gap-2 p-2.5 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] " +
              (flashIds.has(c.id) ? "flash-in" : "")
            }>
              <span className="font-mono text-[11.5px] text-[var(--accent)] min-w-[110px]">{c.part_code ?? "—"}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] truncate font-medium">{c.name}</div>
                <div className="text-[10.5px] text-[var(--muted)] truncate">
                  {c.torque_spec ?? "—"}
                </div>
              </div>
              <div className="flex gap-1">
                <Btn onClick={() => startEdit(c)} className="!px-1.5 !py-0.5 !text-[10px]">…</Btn>
                <Btn variant="danger" onClick={() => remove(c)} className="!px-1.5 !py-0.5 !text-[10px]">×</Btn>
              </div>
            </div>
          ))}
      </div>

      <Modal open={open} onClose={() => setOpen(false)}
             title={editing ? `EDIT — ${editing.name}` : "NEW COMPONENT"}
             footer={<>
               <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
               <Btn variant="primary" disabled={saving} onClick={save}>
                 {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
               </Btn>
             </>}>
        <Input label="Name *" value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Input label="Part Code" value={form.part_code ?? ""} onChange={(e) => setForm({ ...form, part_code: e.target.value })} />
        <Textarea rows={2} label="Description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <Input label="Torque Spec" value={form.torque_spec ?? ""} onChange={(e) => setForm({ ...form, torque_spec: e.target.value })} />
        <Input label="Maintenance Interval" value={form.maintenance_interval ?? ""} onChange={(e) => setForm({ ...form, maintenance_interval: e.target.value })} />
        <Textarea rows={2} label="Safety Notes" value={form.safety_notes ?? ""} onChange={(e) => setForm({ ...form, safety_notes: e.target.value })} />
      </Modal>
    </section>
  );
}
