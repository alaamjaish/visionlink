"use client";

import { useEffect, useState } from "react";

/**
 * Per-panel collapse state, persisted to localStorage so a refresh
 * remembers what the supervisor had hidden.
 *
 *   const [collapsed, toggle] = useCollapsed("sos", false);
 */
export function useCollapsed(
  key: string,
  defaultCollapsed: boolean = false,
): [boolean, () => void] {
  const storageKey = `vl-collapsed:${key}`;
  const [collapsed, setCollapsed] = useState<boolean>(defaultCollapsed);

  // Hydrate from localStorage on mount (avoids SSR mismatch)
  useEffect(() => {
    try {
      const v = localStorage.getItem(storageKey);
      if (v === "1") setCollapsed(true);
      else if (v === "0") setCollapsed(false);
    } catch {
      /* localStorage unavailable — keep default */
    }
  }, [storageKey]);

  function toggle() {
    setCollapsed((cur) => {
      const next = !cur;
      try {
        localStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  return [collapsed, toggle];
}
