"use client";

import { useEffect, useState } from "react";
import { Btn, Pill, Select, Input } from "@/components/Panel";
import { supabase } from "@/lib/supabase";
import type { WearableSettings } from "@/lib/types";

const PROVIDER_OPTS = [
  { value: "openai", label: "🟢 OpenAI gpt-realtime-2" },
  { value: "gemini", label: "🟡 Gemini Live" },
];

const VISION_MODE_OPTS = [
  { value: "snap_on_press", label: "Snap on press (default)" },
  { value: "gemini_video", label: "Continuous video — 1 fps (Gemini only)" },
  { value: "auto_snap_4s", label: "Auto-snap every 4s (any provider)" },
];

export function WearableSettingsPanel() {
  const [s, setS] = useState<WearableSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function load() {
      const { data, error } = await supabase
        .from("wearable_settings")
        .select("*")
        .eq("id", "current")
        .maybeSingle();
      if (!alive) return;
      if (error) {
        setError(error.message);
        return;
      }
      if (data) setS(data as WearableSettings);
    }
    load();

    const ch = supabase
      .channel("wearable_settings_singleton")
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "wearable_settings" },
        (payload) => {
          if (!alive) return;
          const n = payload.new as WearableSettings;
          if (n.id === "current") setS(n);
        },
      )
      .subscribe();

    return () => {
      alive = false;
      supabase.removeChannel(ch);
    };
  }, []);

  async function save() {
    if (!s) return;
    setSaving(true);
    setError(null);
    const { error } = await supabase
      .from("wearable_settings")
      .update({
        b4_provider: s.b4_provider,
        b5_provider: s.b5_provider,
        b5_vision_mode: s.b5_vision_mode,
        sos_photo_interval_s: s.sos_photo_interval_s,
        sos_max_duration_s: s.sos_max_duration_s,
        sos_alert_recipient_role: s.sos_alert_recipient_role,
        sos_provider: s.sos_provider,
        worker_id: s.worker_id,
        worker_name: s.worker_name,
        updated_at: new Date().toISOString(),
      })
      .eq("id", "current");
    setSaving(false);
    if (error) {
      setError(error.message);
      return;
    }
    setSavedAt(new Date().toLocaleTimeString());
  }

  if (!s) {
    return (
      <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl p-5">
        <div className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] font-semibold mb-2">
          Wearable Settings
        </div>
        <div className="text-[13px] text-[var(--muted)]">
          {error
            ? `Failed to load: ${error}`
            : "Loading wearable settings..."}
        </div>
      </section>
    );
  }

  return (
    <section className="bg-[var(--panel)] border border-[var(--border)] rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] m-0 font-semibold">
          Wearable Settings <Pill tone="accent">remote config</Pill>
        </h2>
        <div className="flex items-center gap-2">
          {savedAt && (
            <span className="text-[10.5px] text-[var(--good)]">
              saved {savedAt}
            </span>
          )}
          <Btn variant="primary" onClick={save} disabled={saving}>
            {saving ? "SAVING..." : "SAVE"}
          </Btn>
        </div>
      </div>
      <p className="text-[12px] text-[var(--muted)] mb-4">
        These settings are read by the wearable on every button press.
        Changes propagate within ~200&nbsp;ms via Supabase realtime — no
        restart needed on the device.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Select
          label="B4 — Voice provider"
          options={PROVIDER_OPTS}
          value={s.b4_provider}
          onChange={(e) => setS({ ...s, b4_provider: e.target.value as WearableSettings["b4_provider"] })}
        />
        <Select
          label="B5 — Voice + Vision provider"
          options={PROVIDER_OPTS}
          value={s.b5_provider}
          onChange={(e) => setS({ ...s, b5_provider: e.target.value as WearableSettings["b5_provider"] })}
        />
        <Select
          label="B5 — Vision mode"
          options={VISION_MODE_OPTS}
          value={s.b5_vision_mode}
          onChange={(e) => setS({ ...s, b5_vision_mode: e.target.value as WearableSettings["b5_vision_mode"] })}
        />
        <Select
          label="B6 SOS — Provider"
          options={PROVIDER_OPTS}
          value={s.sos_provider ?? "gemini"}
          onChange={(e) => setS({ ...s, sos_provider: e.target.value as WearableSettings["sos_provider"] })}
        />
        <Input
          label="SOS photo interval (s)"
          type="number"
          min={1}
          max={60}
          value={s.sos_photo_interval_s}
          onChange={(e) => setS({ ...s, sos_photo_interval_s: parseInt(e.target.value || "4", 10) })}
        />
        <Input
          label="SOS max duration (s)"
          type="number"
          min={30}
          max={3600}
          value={s.sos_max_duration_s}
          onChange={(e) => setS({ ...s, sos_max_duration_s: parseInt(e.target.value || "600", 10) })}
        />
        <Input
          label="SOS alert recipient (role)"
          type="text"
          value={s.sos_alert_recipient_role}
          onChange={(e) => setS({ ...s, sos_alert_recipient_role: e.target.value })}
        />
        <Input
          label="Worker ID"
          type="text"
          value={s.worker_id}
          onChange={(e) => setS({ ...s, worker_id: e.target.value })}
        />
        <Input
          label="Worker name"
          type="text"
          value={s.worker_name}
          onChange={(e) => setS({ ...s, worker_name: e.target.value })}
        />
      </div>
      {error && (
        <div className="mt-3 text-[12px] text-[var(--bad)]">
          Save failed: {error}
        </div>
      )}
    </section>
  );
}
