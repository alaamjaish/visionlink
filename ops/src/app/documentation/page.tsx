"use client";

import { useMemo } from "react";
import { SessionsPanel } from "@/components/sections/SessionsPanel";
import { CapturesPanel } from "@/components/sections/CapturesPanel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import type { Session, SessionAsset } from "@/lib/types";

export default function DocumentationPage() {
  const {
    rows: sessions,
    loading: loadingSessions,
    flashIds: sessionFlashIds,
  } = useRealtimeRows<Session>("sessions", {
    orderBy: "started_at",
    limit: 100,
  });

  const {
    rows: assets,
    loading: loadingAssets,
    flashIds: assetFlashIds,
  } = useRealtimeRows<SessionAsset>("session_assets", {
    orderBy: "captured_at",
    limit: 300,
  });

  const stats = useMemo(
    () => ({
      totalSessions: sessions.length,
      openSessions: sessions.filter((s) => s.status === "open").length,
      totalPhotos: assets.filter((a) => a.kind === "photo").length,
      totalVideos: assets.filter((a) => a.kind === "video").length,
      totalVoiceNotes: assets.filter((a) => a.kind === "voice_note").length,
      orphans: assets.filter((a) => !a.session_id).length,
    }),
    [sessions, assets],
  );

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Documentation</h1>
        <p className="text-[var(--muted)] text-sm">
          Shifts and captures from B1 (session toggle), B2 (photo / video),
          B3 (voice note). Streams in realtime — no refresh needed.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Stat
          label="Sessions"
          value={stats.totalSessions}
          sub={stats.openSessions ? `${stats.openSessions} open` : "all closed"}
          accent={stats.openSessions ? "good" : "muted"}
        />
        <Stat label="Photos" icon="📷" value={stats.totalPhotos} />
        <Stat label="Videos" icon="🎬" value={stats.totalVideos} />
        <Stat label="Voice notes" icon="🎙" value={stats.totalVoiceNotes} />
        <Stat label="Total assets" value={assets.length} />
        <Stat
          label="Orphans"
          value={stats.orphans}
          sub="no session"
          accent={stats.orphans ? "warn" : "muted"}
        />
      </div>

      <SessionsPanel
        sessions={sessions}
        assets={assets}
        loading={loadingSessions}
        flashIds={sessionFlashIds}
      />
      <CapturesPanel
        sessions={sessions}
        assets={assets}
        loading={loadingAssets}
        flashIds={assetFlashIds}
      />
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  icon,
  accent = "muted",
}: {
  label: string;
  value: number;
  sub?: string;
  icon?: string;
  accent?: "good" | "muted" | "warn" | "accent";
}) {
  const colors: Record<string, string> = {
    muted: "border-[var(--border)] bg-[var(--panel)]",
    good: "border-[#1c4536] bg-[#0f2a23]",
    warn: "border-[#4d3a18] bg-[#2a210d]",
    accent: "border-[#1c3955] bg-[#0e2034]",
  };
  return (
    <div className={`rounded-xl border p-3 ${colors[accent]}`}>
      <div className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
        {icon ? `${icon} ` : ""}
        {label}
      </div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      {sub && (
        <div className="text-[10.5px] text-[var(--muted)] mt-1">{sub}</div>
      )}
    </div>
  );
}
