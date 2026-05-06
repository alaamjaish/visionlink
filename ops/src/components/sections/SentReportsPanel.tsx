"use client";

import { useState } from "react";
import { Btn, Pill, Modal } from "@/components/Panel";
import { useRealtimeRows } from "@/lib/useRealtimeRows";
import type { SentReport } from "@/lib/types";

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

export function SentReportsPanel() {
  const { rows, loading, flashIds } = useRealtimeRows<SentReport>(
    "sent_reports", { orderBy: "sent_at", limit: 50 },
  );
  const [preview, setPreview] = useState<SentReport | null>(null);

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl flex flex-col min-h-0">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold">
          Sent Reports <span className="text-[var(--accent)] ml-1">· {rows.length}</span>
        </div>
        <span className="text-[10px] text-[var(--muted)]">audit trail of every send_report call</span>
      </header>
      <div className="flex flex-col gap-1.5 p-3 overflow-y-auto max-h-[420px]">
        {loading ? <div className="text-[12px] text-[var(--muted)]">Loading...</div>
          : rows.length === 0 ? <div className="text-[12px] text-[var(--muted)]">No reports sent yet. Tell the agent: "Send the daily ops report to the CEO".</div>
          : rows.map((r) => (
            <div key={r.id} className={
              "flex items-center gap-2 p-2.5 rounded-lg bg-[var(--panel-2)] border border-[var(--border)] cursor-pointer hover:border-[var(--accent)] " +
              (flashIds.has(r.id) ? "flash-in" : "")
            }
              onClick={() => setPreview(r)}>
              <Pill tone={r.status === "sent" ? "good" : "bad"}>
                {r.status}
              </Pill>
              <Pill tone="muted">{r.provider ?? "—"}</Pill>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] font-medium truncate">{r.subject ?? r.template_name ?? "(no subject)"}</div>
                <div className="text-[10.5px] text-[var(--muted)] truncate">
                  to <b>{r.recipient_name ?? r.recipient_email ?? "—"}</b>
                  {r.recipient_role && <span> · {r.recipient_role}</span>}
                  {" · "}{timeAgo(r.sent_at)} ago
                </div>
              </div>
            </div>
          ))}
      </div>

      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title="EMAIL PREVIEW"
        footer={<Btn variant="primary" onClick={() => setPreview(null)}>CLOSE</Btn>}
      >
        {preview && (
          <>
            <div className="text-[11px] text-[var(--muted)]">
              <div><b>To:</b> {preview.recipient_name} &lt;{preview.recipient_email}&gt; ({preview.recipient_role ?? "—"})</div>
              <div><b>Subject:</b> {preview.subject}</div>
              <div><b>Template:</b> {preview.template_name}</div>
              <div><b>Sent:</b> {new Date(preview.sent_at).toLocaleString()} via {preview.provider}</div>
              {preview.error && <div className="text-[var(--bad)]"><b>Error:</b> {preview.error}</div>}
            </div>
            <div className="border border-[var(--border)] rounded-md p-3 bg-white text-black text-[13px] leading-relaxed"
                 dangerouslySetInnerHTML={{ __html: preview.body_html ?? "" }} />
          </>
        )}
      </Modal>
    </section>
  );
}
