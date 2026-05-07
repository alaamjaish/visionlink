"use client";

import { useState } from "react";
import { Btn, Pill, Modal, Textarea } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { SosEvent } from "@/lib/types";

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

export function SosPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<SosEvent>(
    "sos_events",
    { orderBy: "triggered_at", limit: 30 },
  );

  const [resolveTarget, setResolveTarget] = useState<SosEvent | null>(null);
  const [resolveReason, setResolveReason] = useState("");
  const [resolverName, setResolverName] = useState("Supervisor");
  const [resolving, setResolving] = useState(false);

  const open = rows.filter((r) => !r.resolved);

  async function shutdown(ev: SosEvent) {
    setResolving(true);
    const { error } = await supabase
      .from("sos_events")
      .update({
        resolved: true,
        resolved_at: new Date().toISOString(),
        resolved_by: resolverName.trim() || "Supervisor",
        reason: resolveReason.trim() || "shutdown via ops dashboard",
      })
      .eq("id", ev.id);
    setResolving(false);
    if (error) {
      alert(`Shutdown failed: ${error.message}`);
      return;
    }
    setResolveTarget(null);
    setResolveReason("");
  }

  return (
    <section
      className={
        "bg-[var(--panel)] border rounded-xl p-5 transition-colors " +
        (open.length > 0
          ? "border-[var(--bad)] shadow-[0_0_24px_rgba(255,90,106,0.25)] animate-pulse-slow"
          : "border-[var(--border)]")
      }
    >
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] m-0 font-semibold">
          🆘 SOS Panic Mode
          {open.length > 0 ? (
            <Pill tone="bad"> {open.length} ACTIVE</Pill>
          ) : (
            <Pill tone="muted"> idle</Pill>
          )}
        </h2>
      </div>

      {loading && (
        <div className="text-[13px] text-[var(--muted)]">Loading SOS events...</div>
      )}

      {!loading && rows.length === 0 && (
        <div className="text-[13px] text-[var(--muted)]">
          No SOS events yet. Worker can double-click B6 to trigger.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {rows.map((r) => {
          const isFlash = flashIds.has(r.id);
          const isOpen = !r.resolved;
          return (
            <div
              key={r.id}
              className={
                "rounded-lg border p-3 " +
                (isOpen
                  ? "border-[var(--bad)] bg-[#260a10]"
                  : "border-[var(--border)] bg-[var(--panel-2)]") +
                (isFlash ? " ring-2 ring-[var(--accent)]" : "")
              }
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Pill tone={isOpen ? "bad" : "good"}>
                    {isOpen ? "🚨 ACTIVE" : "✓ resolved"}
                  </Pill>
                  <span className="text-[12px] text-[var(--text)] font-semibold">
                    {r.worker_name || r.worker_id}
                  </span>
                  <span className="text-[11px] text-[var(--muted)]">
                    {timeAgo(r.triggered_at)} ago
                  </span>
                  <span className="text-[11px] text-[var(--muted)]">
                    · {r.frames_sent} frame{r.frames_sent === 1 ? "" : "s"}
                  </span>
                  {r.email_sent && (
                    <Pill tone="accent">email sent</Pill>
                  )}
                </div>
                {isOpen && (
                  <Btn variant="danger" onClick={() => setResolveTarget(r)}>
                    🛑 SHUT OFF
                  </Btn>
                )}
                {!isOpen && r.resolved_by && (
                  <span className="text-[11px] text-[var(--muted)]">
                    by {r.resolved_by}
                  </span>
                )}
              </div>
              {r.live_transcript && (
                <div className="mt-2 text-[12px] text-[var(--text)] font-mono whitespace-pre-wrap">
                  {r.live_transcript}
                </div>
              )}
              {!isOpen && r.reason && (
                <div className="mt-1 text-[11px] text-[var(--muted)] italic">
                  reason: {r.reason}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <Modal
        open={!!resolveTarget}
        onClose={() => setResolveTarget(null)}
        title="🛑 Shut off SOS"
        footer={
          <>
            <Btn variant="ghost" onClick={() => setResolveTarget(null)}>
              CANCEL
            </Btn>
            <Btn
              variant="danger"
              onClick={() => resolveTarget && shutdown(resolveTarget)}
              disabled={resolving}
            >
              {resolving ? "SHUTTING DOWN..." : "CONFIRM SHUTDOWN"}
            </Btn>
          </>
        }
      >
        <div className="text-[12.5px] text-[var(--muted)]">
          This will tell the wearable to stop the SOS stream. The worker
          should hear a confirmation tone. Logs your name + reason for the
          audit trail.
        </div>
        <Textarea
          label="Your name"
          value={resolverName}
          onChange={(e) => setResolverName(e.target.value)}
          rows={1}
        />
        <Textarea
          label="Reason / outcome"
          placeholder="e.g. arrived on scene, false alarm, worker safe"
          value={resolveReason}
          onChange={(e) => setResolveReason(e.target.value)}
          rows={3}
        />
      </Modal>
    </section>
  );
}
