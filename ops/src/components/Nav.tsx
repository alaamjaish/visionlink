"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Agent" },
  { href: "/documentation", label: "Documentation" },
];

export default function Nav() {
  const pathname = usePathname();
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
        <nav className="flex items-center gap-1 ml-2">
          {links.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname?.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={
                  "px-3 py-1.5 rounded-md text-[12px] tracking-wider uppercase border transition-colors " +
                  (active
                    ? "bg-[var(--panel)] border-[var(--accent)] text-[var(--text)]"
                    : "bg-transparent border-transparent text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--border)]")
                }
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-[11px] text-[var(--muted)] font-mono">
          <span className="inline-block w-2 h-2 rounded-full bg-[var(--good)] shadow-[0_0_8px_var(--good)]"></span>
          live · supabase realtime
        </div>
      </div>
    </header>
  );
}
