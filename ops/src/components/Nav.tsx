"use client";

import Link from "next/link";

export default function Nav() {
  return (
    <header
      className="border-b border-[var(--border)]"
      style={{ background: "linear-gradient(90deg, #0f1724, #0b0f14)" }}
    >
      <div className="max-w-[1500px] mx-auto px-8 py-4 flex items-center gap-6">
        <Link href="/" className="font-bold tracking-[0.16em] uppercase text-[15px]">
          VISION<span className="text-[var(--accent)]">LINK</span>
          <span className="text-[var(--muted)] font-normal"> · ops</span>
        </Link>
        <div className="ml-auto flex items-center gap-3 text-[11px] text-[var(--muted)] font-mono">
          <span className="inline-block w-2 h-2 rounded-full bg-[var(--good)] shadow-[0_0_8px_var(--good)]"></span>
          live · supabase realtime
        </div>
      </div>
    </header>
  );
}
