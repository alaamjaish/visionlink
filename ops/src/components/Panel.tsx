import React from "react";

export function Panel({
  title,
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={
        "bg-[var(--panel)] border border-[var(--border)] rounded-xl p-5 " + className
      }
    >
      {(title || right) && (
        <div className="flex items-center justify-between mb-3">
          {title && (
            <h2 className="text-[11px] tracking-[0.14em] uppercase text-[var(--muted)] m-0 font-semibold">
              {title}
            </h2>
          )}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Btn({
  variant = "ghost",
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "danger" | "ghost";
}) {
  const base =
    "inline-flex items-center gap-2 px-3 py-2 rounded-md text-[12px] font-semibold tracking-wider " +
    "transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const styles = {
    primary:
      "bg-[var(--accent)] text-[#041321] border border-[var(--accent)] hover:brightness-110",
    danger:
      "bg-[var(--bad)] text-[#1a0408] border border-[var(--bad)] hover:brightness-110",
    ghost:
      "bg-transparent text-[var(--text)] border border-[var(--border)] hover:border-[var(--accent)]",
  } as const;
  return (
    <button {...rest} className={`${base} ${styles[variant]} ${className}`}>
      {children}
    </button>
  );
}

export function Pill({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "good" | "bad" | "warn" | "accent";
  children: React.ReactNode;
}) {
  const tones = {
    muted: "bg-[var(--panel-2)] text-[var(--muted)] border-[var(--border)]",
    good: "bg-[#0f2a23] text-[var(--good)] border-[#1c4536]",
    bad: "bg-[#2a0d12] text-[var(--bad)] border-[#4d1922]",
    warn: "bg-[#2a210d] text-[var(--warn)] border-[#4d3a18]",
    accent: "bg-[#0e2034] text-[var(--accent)] border-[#1c3955]",
  };
  return (
    <span
      className={
        "inline-block px-2 py-0.5 rounded-full text-[10.5px] font-semibold uppercase tracking-wider border " +
        tones[tone]
      }
    >
      {children}
    </span>
  );
}

export function Input(
  props: React.InputHTMLAttributes<HTMLInputElement> & { label?: string },
) {
  const { label, className = "", ...rest } = props;
  return (
    <label className="flex flex-col gap-1 text-[11px] tracking-[0.1em] uppercase text-[var(--muted)]">
      {label}
      <input
        {...rest}
        className={
          "bg-[var(--panel-2)] border border-[var(--border)] rounded-md px-3 py-2 " +
          "text-[13px] text-[var(--text)] focus:outline-1 focus:outline-[var(--accent)] " +
          "focus:border-[var(--accent)] " + className
        }
      />
    </label>
  );
}

export function Textarea(
  props: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string },
) {
  const { label, className = "", ...rest } = props;
  return (
    <label className="flex flex-col gap-1 text-[11px] tracking-[0.1em] uppercase text-[var(--muted)]">
      {label}
      <textarea
        {...rest}
        className={
          "bg-[var(--panel-2)] border border-[var(--border)] rounded-md px-3 py-2 " +
          "text-[13px] text-[var(--text)] focus:outline-1 focus:outline-[var(--accent)] " +
          "focus:border-[var(--accent)] " + className
        }
      />
    </label>
  );
}

export function Select(
  props: React.SelectHTMLAttributes<HTMLSelectElement> & {
    label?: string;
    options: { value: string; label: string }[];
  },
) {
  const { label, options, className = "", ...rest } = props;
  return (
    <label className="flex flex-col gap-1 text-[11px] tracking-[0.1em] uppercase text-[var(--muted)]">
      {label}
      <select
        {...rest}
        className={
          "bg-[var(--panel-2)] border border-[var(--border)] rounded-md px-3 py-2 " +
          "text-[13px] text-[var(--text)] focus:outline-1 focus:outline-[var(--accent)] " +
          "focus:border-[var(--accent)] " + className
        }
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center pt-[8vh]"
      onClick={onClose}
    >
      <div
        className="w-[min(640px,92vw)] max-h-[84vh] flex flex-col bg-[var(--panel)] border border-[var(--border)] rounded-xl shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border)]">
          <h3 className="text-[13px] uppercase tracking-[0.14em] font-bold m-0">
            {title}
          </h3>
          <Btn variant="ghost" onClick={onClose} className="!px-3 !py-1">
            CLOSE
          </Btn>
        </div>
        <div className="overflow-y-auto px-5 py-4 flex flex-col gap-4">
          {children}
        </div>
        {footer && (
          <div className="flex justify-end gap-2 px-5 py-3 border-t border-[var(--border)] bg-[var(--panel-2)] rounded-b-xl">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
