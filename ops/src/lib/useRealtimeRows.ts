"use client";

import { useEffect, useRef, useState } from "react";
import { supabase } from "./supabase";

type WithId = { id: string };

export function useRealtimeRows<T extends WithId>(
  table: string,
  options: { orderBy?: string; ascending?: boolean; limit?: number } = {},
) {
  const orderBy = options.orderBy ?? "created_at";
  const ascending = options.ascending ?? false;
  const limit = options.limit ?? 200;

  const [rows, setRows] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flashIds, setFlashIds] = useState<Set<string>>(new Set());
  const flashTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  function flash(id: string) {
    setFlashIds((s) => {
      const n = new Set(s);
      n.add(id);
      return n;
    });
    const prior = flashTimers.current.get(id);
    if (prior) clearTimeout(prior);
    const t = setTimeout(() => {
      setFlashIds((s) => {
        const n = new Set(s);
        n.delete(id);
        return n;
      });
      flashTimers.current.delete(id);
    }, 1500);
    flashTimers.current.set(id, t);
  }

  useEffect(() => {
    let alive = true;
    const log = (...args: unknown[]) =>
      console.log(`[rt:${table}]`, ...args);

    log("mount, fetching initial rows");

    (async () => {
      try {
        const t0 = performance.now();
        const { data, error } = await supabase
          .from(table)
          .select("*")
          .order(orderBy, { ascending })
          .limit(limit);
        const dt = Math.round(performance.now() - t0);
        if (!alive) {
          log(`fetch resolved after unmount (${dt}ms)`);
          return;
        }
        if (error) {
          console.error(`[rt:${table}] fetch error`, error);
          setError(`${error.code ?? ""} ${error.message}`.trim());
        } else {
          log(`fetched ${data?.length ?? 0} rows in ${dt}ms`);
          setRows((data ?? []) as T[]);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        console.error(`[rt:${table}] fetch threw:`, e);
        if (alive) setError(msg);
      } finally {
        if (alive) setLoading(false);
      }
    })();

    const channel = supabase
      .channel(`realtime-${table}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table },
        (payload) => {
          if (!alive) return;
          if (payload.eventType === "INSERT") {
            const row = payload.new as T;
            setRows((prev) => {
              if (prev.some((r) => r.id === row.id)) return prev;
              return ascending ? [...prev, row] : [row, ...prev];
            });
            flash(row.id);
          } else if (payload.eventType === "UPDATE") {
            const row = payload.new as T;
            setRows((prev) => prev.map((r) => (r.id === row.id ? row : r)));
            flash(row.id);
          } else if (payload.eventType === "DELETE") {
            const oldRow = payload.old as WithId;
            setRows((prev) => prev.filter((r) => r.id !== oldRow.id));
          }
        },
      )
      .subscribe((status) => log(`realtime status: ${status}`));

    return () => {
      alive = false;
      log("unmount");
      supabase.removeChannel(channel);
      for (const t of flashTimers.current.values()) clearTimeout(t);
      flashTimers.current.clear();
    };
  }, [table, orderBy, ascending, limit]);

  return { rows, loading, error, flashIds };
}
