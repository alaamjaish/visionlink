"use client";

import { useMemo, useState } from "react";
import { Panel, Pill, Modal } from "@/components/Panel";
import { supabase } from "@/lib/supabase";
import type { Session, SessionAsset } from "@/lib/types";

const BUCKET = "session-assets";

function publicUrl(path: string): string | null {
  if (!path) return null;
  const { data } = supabase.storage.from(BUCKET).getPublicUrl(path);
  return data?.publicUrl || null;
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

type Filter = "all" | "photo" | "video" | "voice_note" | "orphan";

export function CapturesPanel({
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
  const [filter, setFilter] = useState<Filter>("all");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const sessionLabel = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of sessions) {
      m.set(s.id, s.label || `Session ${s.id.slice(0, 8)}`);
    }
    return m;
  }, [sessions]);

  const counts = useMemo(
    () => ({
      all: assets.length,
      photo: assets.filter((a) => a.kind === "photo").length,
      video: assets.filter((a) => a.kind === "video").length,
      voice_note: assets.filter((a) => a.kind === "voice_note").length,
      orphan: assets.filter((a) => !a.session_id).length,
    }),
    [assets],
  );

  const visible = useMemo(() => {
    if (filter === "all") return assets;
    if (filter === "orphan") return assets.filter((a) => !a.session_id);
    return assets.filter((a) => a.kind === filter);
  }, [assets, filter]);

  const tabs: { key: Filter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "photo", label: "📷 Photos" },
    { key: "video", label: "🎬 Videos" },
    { key: "voice_note", label: "🎙 Voice notes" },
    { key: "orphan", label: "⚠ Orphans" },
  ];

  return (
    <Panel title="Captures">
      <div className="flex gap-2 flex-wrap mb-3">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setFilter(t.key)}
            className={
              "px-3 py-1.5 rounded-md text-[12px] tracking-wider uppercase border transition-colors " +
              (filter === t.key
                ? "bg-[var(--panel)] border-[var(--accent)] text-[var(--text)]"
                : "bg-transparent border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)]")
            }
          >
            {t.label}{" "}
            <span className="ml-1 text-[10px] opacity-70">
              {counts[t.key]}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-[var(--muted)] text-sm">Loading captures...</p>
      ) : visible.length === 0 ? (
        <p className="text-[var(--muted)] text-sm">
          No captures match this filter.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {visible.map((a) => {
            const url = publicUrl(a.storage_path);
            const isFlash = flashIds.has(a.id);
            const sessionName = a.session_id
              ? sessionLabel.get(a.session_id)
              : null;
            return (
              <div
                key={a.id}
                className={
                  "rounded-lg border bg-[var(--panel-2)] p-2 flex flex-col gap-2 " +
                  (a.session_id
                    ? "border-[var(--border)]"
                    : "border-[#4d3a18]") +
                  (isFlash ? " ring-2 ring-[var(--accent)]" : "")
                }
              >
                {a.kind === "photo" && url && (
                  <button
                    type="button"
                    onClick={() => setPreviewUrl(url)}
                    className="block w-full aspect-video bg-black rounded overflow-hidden hover:opacity-90 cursor-zoom-in"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={url}
                      alt={a.storage_path}
                      className="w-full h-full object-contain"
                    />
                  </button>
                )}
                {a.kind === "video" && url && (
                  <video
                    src={url}
                    controls
                    preload="metadata"
                    className="w-full aspect-video bg-black rounded"
                  />
                )}
                {a.kind === "voice_note" && url && (
                  <audio
                    src={url}
                    controls
                    preload="metadata"
                    className="w-full"
                  />
                )}
                {!url && (
                  <div className="w-full aspect-video bg-black rounded flex items-center justify-center text-[var(--bad)] text-[11px]">
                    storage URL unavailable
                  </div>
                )}

                <div className="flex items-center justify-between gap-2 flex-wrap text-[11px]">
                  <div className="flex items-center gap-1.5">
                    <Pill tone={a.session_id ? "accent" : "warn"}>
                      {a.kind.replace("_", " ")}
                    </Pill>
                    {!a.session_id && <Pill tone="warn">orphan</Pill>}
                    {a.duration_s ? (
                      <span className="text-[var(--muted)]">
                        {a.duration_s.toFixed(1)}s
                      </span>
                    ) : null}
                  </div>
                  <span className="text-[var(--muted)]">
                    {fmtTime(a.captured_at)}
                  </span>
                </div>
                <div className="text-[10.5px] text-[var(--muted)] truncate">
                  {sessionName ? `↳ ${sessionName}` : "no session"}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Modal
        open={!!previewUrl}
        onClose={() => setPreviewUrl(null)}
        title="Photo preview"
      >
        {previewUrl && (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={previewUrl}
            alt="full preview"
            className="w-full max-h-[70vh] object-contain bg-black rounded"
          />
        )}
      </Modal>
    </Panel>
  );
}
