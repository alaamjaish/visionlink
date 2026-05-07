"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Btn, Pill, Modal, Textarea } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import { supabase } from "@/lib/supabase";
import type { SosEvent } from "@/lib/types";

// Public URL builder — bucket 'session-assets' is public, so we can
// construct the URL directly without signing.
function publicUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  const { data } = supabase.storage.from("session-assets").getPublicUrl(path);
  return data?.publicUrl || null;
}

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

// ----------------------------------------------------------------
// Web Audio alarm — repeating beeps while at least one SOS is open.
// Uses Web Audio API so we don't ship an mp3. User can toggle it off.
// ----------------------------------------------------------------
function useSosAlarm(active: boolean, muted: boolean) {
  const ctxRef = useRef<AudioContext | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    function beep() {
      try {
        const Ctx = (window as unknown as {
          AudioContext?: typeof AudioContext;
          webkitAudioContext?: typeof AudioContext;
        }).AudioContext || (window as unknown as {
          webkitAudioContext: typeof AudioContext;
        }).webkitAudioContext;
        if (!Ctx) return;
        if (!ctxRef.current) ctxRef.current = new Ctx();
        const ctx = ctxRef.current;
        const now = ctx.currentTime;

        // Two-tone urgent bleep: 880Hz for 200ms, 660Hz for 200ms
        for (const [freq, start, dur] of [
          [880, 0.0, 0.2],
          [660, 0.25, 0.2],
        ] as const) {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "square";
          osc.frequency.setValueAtTime(freq, now + start);
          gain.gain.setValueAtTime(0, now + start);
          gain.gain.linearRampToValueAtTime(0.18, now + start + 0.02);
          gain.gain.linearRampToValueAtTime(0, now + start + dur);
          osc.connect(gain).connect(ctx.destination);
          osc.start(now + start);
          osc.stop(now + start + dur + 0.05);
        }
      } catch {
        /* suspended context — user hasn't interacted with page yet */
      }
    }

    if (active && !muted) {
      beep();                            // immediate
      intervalRef.current = setInterval(beep, 1500);   // every 1.5s
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [active, muted]);
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
  const [muted, setMuted] = useState(false);

  const open = useMemo(() => rows.filter((r) => !r.resolved), [rows]);
  const armed = open.length > 0;

  useSosAlarm(armed, muted);

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
        "rounded-xl p-5 transition-all duration-300 " +
        (armed
          ? "bg-[#1a0509] border-2 border-[var(--bad)] shadow-[0_0_36px_rgba(255,90,106,0.55)] sos-pulse"
          : "bg-[var(--panel)] border border-[var(--border)]")
      }
    >
      <style jsx>{`
        @keyframes sos-pulse-ring {
          0%   { box-shadow: 0 0 36px rgba(255,90,106,0.45), inset 0 0 0 0 rgba(255,90,106,0.0); }
          50%  { box-shadow: 0 0 60px rgba(255,90,106,0.85), inset 0 0 0 4px rgba(255,90,106,0.20); }
          100% { box-shadow: 0 0 36px rgba(255,90,106,0.45), inset 0 0 0 0 rgba(255,90,106,0.0); }
        }
        @keyframes sos-blink {
          0%, 49%  { opacity: 1; }
          50%, 100% { opacity: 0.45; }
        }
        :global(.sos-pulse) { animation: sos-pulse-ring 1.2s ease-in-out infinite; }
        .sos-blink { animation: sos-blink 0.8s steps(2, jump-none) infinite; }
      `}</style>

      {/* HEADER — much bigger when armed */}
      <div
        className={
          "flex items-center justify-between mb-4 " +
          (armed ? "flex-wrap gap-3" : "")
        }
      >
        {armed ? (
          <>
            <div className="flex items-center gap-3">
              <span className="sos-blink text-4xl">🆘</span>
              <div>
                <div className="text-[var(--bad)] font-extrabold tracking-[0.18em] uppercase text-xl leading-tight">
                  SOS PANIC MODE ACTIVE
                </div>
                <div className="text-[12px] text-[var(--muted)] mt-1">
                  {open.length} active alert{open.length === 1 ? "" : "s"} · supervisor must respond
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Btn variant="ghost" onClick={() => setMuted((v) => !v)}>
                {muted ? "🔔 UNMUTE ALARM" : "🔕 MUTE ALARM"}
              </Btn>
            </div>
          </>
        ) : (
          <h2 className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] m-0 font-semibold">
            🆘 SOS Panic Mode <Pill tone="muted">idle</Pill>
          </h2>
        )}
      </div>

      {loading && (
        <div className="text-[13px] text-[var(--muted)]">Loading SOS events...</div>
      )}

      {!loading && rows.length === 0 && (
        <div className="text-[13px] text-[var(--muted)]">
          No SOS events yet. Worker can double-click B6 to trigger.
        </div>
      )}

      <div className="flex flex-col gap-4">
        {rows.map((r) => {
          const isFlash = flashIds.has(r.id);
          const isOpen = !r.resolved;
          const frameUrl = publicUrl(r.last_frame_path);
          return (
            <div
              key={r.id}
              className={
                "rounded-lg border p-4 " +
                (isOpen
                  ? "border-2 border-[var(--bad)] bg-[#260a10]"
                  : "border-[var(--border)] bg-[var(--panel-2)]") +
                (isFlash ? " ring-2 ring-[var(--accent)]" : "")
              }
            >
              {/* LIVE FRAME — only when armed and we have a path */}
              {isOpen && frameUrl && (
                <div className="mb-3 rounded-md overflow-hidden border border-[var(--bad)] bg-black">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    key={frameUrl}    /* re-mount on path change so the new frame replaces the old */
                    src={frameUrl}
                    alt="live SOS camera frame"
                    className="block w-full max-h-[420px] object-contain"
                  />
                  <div className="flex items-center justify-between px-3 py-1.5 text-[10.5px] tracking-[0.1em] uppercase text-[var(--bad)] bg-[#1a0509]">
                    <span>🔴 LIVE · frame {r.frames_sent}</span>
                    <span className="text-[var(--muted)]">{r.last_frame_path}</span>
                  </div>
                </div>
              )}

              {isOpen && !frameUrl && (
                <div className="mb-3 rounded-md border border-dashed border-[var(--bad)] bg-[#1a0509] p-3 text-[12px] text-[var(--muted)]">
                  📷 Waiting for first frame... ({r.frames_sent} sent)
                </div>
              )}

              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <Pill tone={isOpen ? "bad" : "good"}>
                    {isOpen ? "🚨 ACTIVE" : "✓ resolved"}
                  </Pill>
                  <span className={
                    "text-[var(--text)] font-semibold " +
                    (isOpen ? "text-[14px]" : "text-[12px]")
                  }>
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
                <div className="mt-3 text-[12.5px] text-[var(--text)] font-mono whitespace-pre-wrap bg-[#0c0306] border border-[var(--border)] rounded-md p-3 max-h-[160px] overflow-y-auto">
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
