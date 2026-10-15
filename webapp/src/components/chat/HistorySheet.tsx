"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/shadcn/sheet";
import { Button } from "@/components/ui/Button";
import { fetchCoachActions } from "@/lib/api";
import { ActionResult } from "./Actions";

/* History (spec: coach-conversation): the changes made from the
   conversation, newest first, each with Undo while it's still valid. */
export function HistorySheet() {
  const [open, setOpen] = React.useState(false);
  const actions = useQuery({ queryKey: ["coach-actions"], queryFn: fetchCoachActions, enabled: open });
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="secondary" iconLeft="history" data-testid="history-button">History</Button>
      </SheetTrigger>
      <SheetContent side="right" data-testid="history-sheet" style={{ width: "min(440px, 100vw)", background: "var(--bg-web)" }}>
        <SheetHeader>
          <SheetTitle style={{ font: "700 20px var(--font-sans)", color: "var(--text-strong)" }}>History</SheetTitle>
          <SheetDescription>Changes you confirmed in the conversation. Undo works while nothing they touched has changed.</SheetDescription>
        </SheetHeader>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "0 16px 16px", overflowY: "auto" }}>
          {actions.isError && <div role="alert" style={{ font: "500 14px var(--font-sans)", color: "var(--expense)" }}>We couldn&apos;t load your history.</div>}
          {actions.data?.length === 0 && (
            <div style={{ font: "500 14px/1.5 var(--font-sans)", color: "var(--text-muted)" }}>
              Changes you confirm here show up in this list. Try &quot;gasté 12 en el café&quot;.
            </div>
          )}
          {actions.data?.map((a) => (
            <div key={a.id} data-testid="history-item" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
                {new Date(a.applied_at ?? a.created_at).toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" })}
              </span>
              <ActionResult action={a} />
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
