"use client";

import { IncidentsPanel } from "@/components/sections/IncidentsPanel";
import { TasksPanel } from "@/components/sections/TasksPanel";
import { PartsPanel } from "@/components/sections/PartsPanel";
import { ComponentsPanel } from "@/components/sections/ComponentsPanel";
import { ManagersPanel } from "@/components/sections/ManagersPanel";
import { ReportTemplatesPanel } from "@/components/sections/ReportTemplatesPanel";
import { SentReportsPanel } from "@/components/sections/SentReportsPanel";

export default function CommandCenter() {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Command Center</h1>
        <p className="text-[var(--muted)] text-sm">
          One screen, every live table. Every change from the wearable
          (or this dashboard) propagates to all connected viewers within ~200ms.
        </p>
      </div>

      <div className="text-[10.5px] tracking-[0.14em] uppercase text-[var(--muted)] mt-2">Operations</div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <IncidentsPanel />
        <TasksPanel />
        <PartsPanel />
        <ComponentsPanel />
      </div>

      <div className="text-[10.5px] tracking-[0.14em] uppercase text-[var(--muted)] mt-4">Communications</div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <ManagersPanel />
        <ReportTemplatesPanel />
      </div>
      <SentReportsPanel />
    </div>
  );
}
