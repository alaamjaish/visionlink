"use client";

import { useMemo, useState } from "react";
import { Panel, Pill } from "@/components/Panel";
import type { Session, SessionAsset } from "@/lib/types";

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDuration(start: string, end: string | null) {
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  const s = Math.max(0, Math.floor((endMs - startMs) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

const KIND_ICON: Record<SessionAsset["kind"], string> = {
  photo: "📷",
  video: "🎬",
  voice_note: "🎙",
};

export function SessionsPanel({
  sessions,
  assets,
  loading,
  flashIds,
}: {
  sessions: Session[];
  assets: SessionAsset[];
  loading: boolean;
  flashIds: Set<string>;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const assetsBySession = useMemo(() => {
    const map = new Map<string, SessionAsset[]>();
    for (const a of assets) {
      if (!a.session_id) continue;
      const arr = map.get(a.session_id);
      if (arr) arr.push(a);
      else map.set(a.session_id, [a]);
    }
    return map;
  }, [assets]);

  return (
    <Panel title="Sessions">
      {loading ? (
        <p className="text-[var(--muted)] text-sm">Loading sessions...</p>
      ) : sessions.length === 0 ? (
        <p className="text-[var(--muted)] text-sm">
          No sessions yet. Worker presses B1 to open one.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {sessions.map((s) => {
            const isOpen = s.status === "open";
            const isExpanded = expanded === s.id;
            const sessionAssets = assetsBySession.get(s.id) ?? [];
            const counts = {
              photo: sessionAssets.filter((a) => a.kind === "photo").length,
              video: sessionAssets.filter((a) => a.kind === "video").length,
              voice_note: sessionAssets.filter(
                (a) => a.kind === "voice_note",
              ).length,
            };
            const isFlash = flashIds.has(s.id);
            return (
              <div
                key={s.id}
                className={
                  "rounded-lg border " +
                  (isOpen
                    ? "border-2 border-[var(--good)] bg-[#0f2a23]"
                    : "border-[var(--border)] bg-[var(--panel-2)]") +
                  (isFlash ? " ring-2 ring-[var(--accent)]" : "")
                }
              >
                <button
                  type="button"
                  onClick={() => setExpanded(isExpanded ? null : s.id)}
                  className="w-full flex items-start gap-3 p-3 text-left hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                >
                  <span className="text-[var(--muted)] text-sm mt-0.5">
                    {isExpanded ? "▾" : "▸"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Pill tone={isOpen ? "good" : "muted"}>
                        {isOpen ? "● OPEN" : "closed"}
                      </Pill>
                      <span className="text-[14px] font-medium">
                        {s.label || `Session ${s.id.slice(0, 8)}`}
                      </span>
                    </div>
                    <div className="text-[11px] text-[var(--muted)] mt-1">
                      {s.worker_name || s.worker_id} · started{" "}
                      {fmtTime(s.started_at)} ·{" "}
                      {fmtDuration(s.started_at, s.ended_at)}
                      {s.ended_at ? ` · ended ${fmtTime(s.ended_at)}` : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-[var(--muted)] min-w-[140px] justify-end">
                    {counts.photo > 0 && <span>📷 {counts.photo}</span>}
                    {counts.video > 0 && <span>🎬 {counts.video}</span>}
                    {counts.voice_note > 0 && (
                      <span>🎙 {counts.voice_note}</span>
                    )}
                    {sessionAssets.length === 0 && (
                      <span className="opacity-60">no captures</span>
                    )}
                  </div>
                </button>
                {isExpanded && (
                  <div className="border-t border-[var(--border)] bg-[var(--panel)] p-3">
                    {sessionAssets.length === 0 ? (
                      <p className="text-[11px] text-[var(--muted)]">
                        No captures in this session.
                      </p>
                    ) : (
                      <ul className="flex flex-col gap-1.5 text-[12px]">
                        {sessionAssets.map((a) => (
                          <li
                            key={a.id}
                            className="flex items-center gap-2"
                          >
                            <span>{KIND_ICON[a.kind]}</span>
                            <span className="text-[var(--text)] truncate flex-1 font-mono text-[11px]">
                              {a.storage_path}
                            </span>
                            <span className="text-[var(--muted)] text-[10.5px]">
                              {fmtTime(a.captured_at)}
                              {a.duration_s
                                ? ` · ${a.duration_s.toFixed(1)}s`
                                : ""}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}
