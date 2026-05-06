"use client";

import { useState } from "react";
import { Btn, Pill, Modal, Input, Textarea } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { Manager } from "@/lib/types";

const empty: Partial<Manager> = {
  name: "",
  email: "",
  role: "",
  notes: "",
};

export function ManagersPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<Manager>(
    "managers", { orderBy: "created_at", limit: 50 },
  );
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Manager | null>(null);
  const [form, setForm] = useState<Partial<Manager>>(empty);
  const [saving, setSaving] = useState(false);

  function startCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function startEdit(m: Manager) { setEditing(m); setForm({ ...m }); setOpen(true); }

  async function save() {
    if (!form.name?.trim() || !form.email?.trim()) {
      alert("Name and email required"); return;
    }
    setSaving(true);
    const payload = {
      name: form.name?.trim(),
      email: form.email?.trim(),
      role: form.role?.trim() || null,
      notes: form.notes?.trim() || null,
    };
    const { error } = editing
      ? await supabase.from("managers").update(payload).eq("id", editing.id)
      : await supabase.from("managers").insert(payload);
    setSaving(false);
    if (error) alert("Save failed: " + error.message); else setOpen(false);
  }
  async function remove(m: Manager) {
    if (!confirm(`Delete ${m.name}?`)) return;
    const { error } = await supabase.from("managers").delete().eq("id", m.id);
    if (error) alert("Delete failed: " + error.message);
  }

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold">
          Managers <span className="text-[var(--accent)] ml-1">· {rows.length}</span>
        </div>
        <Btn variant="primary" onClick={startCreate} className="!px-3 !py-1 !text-[11px]">+ NEW</Btn>
      </header>
      <div className="flex flex-col gap-1.5 p-3 overflow-y-auto max-h-[420px]">
        {loading ? <div className="text-[12px] text-[var(--muted)]">Loading...</div>
          : rows.length === 0 ? <div className="text-[12px] text-[var(--muted)]">No managers — add one before sending reports.</div>
          : rows.map((m) => (
            <div key={m.id} className={
              "flex items-center gap-2 p-2.5 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] " +
              (flashIds.has(m.id) ? "flash-in" : "")
            }>
              <Pill tone="accent">{m.role ?? "—"}</Pill>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] font-medium truncate">{m.name}</div>
                <div className="text-[10.5px] text-[var(--muted)] truncate">{m.email}</div>
              </div>
              <div className="flex gap-1">
                <Btn onClick={() => startEdit(m)} className="!px-1.5 !py-0.5 !text-[10px]">…</Btn>
                <Btn variant="danger" onClick={() => remove(m)} className="!px-1.5 !py-0.5 !text-[10px]">×</Btn>
              </div>
            </div>
          ))}
      </div>

      <Modal open={open} onClose={() => setOpen(false)}
             title={editing ? `EDIT — ${editing.name}` : "NEW MANAGER"}
             footer={<>
               <Btn onClick={() => setOpen(false)}>CANCEL</Btn>
               <Btn variant="primary" disabled={saving} onClick={save}>
                 {saving ? "SAVING..." : editing ? "SAVE" : "CREATE"}
               </Btn>
             </>}>
        <Input label="Name *" value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Input type="email" label="Email *" value={form.email ?? ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Input label="Role (CEO, supervisor, accountant, …)" value={form.role ?? ""} onChange={(e) => setForm({ ...form, role: e.target.value })} />
        <Textarea rows={2} label="Notes" value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      </Modal>
    </section>
  );
}
