"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import { IncomeBreakdown } from "@/components/budget/IncomeBreakdown";
import { CoachCapsule } from "@/components/ui/CoachCapsule";
import { Icon } from "@/components/ui/Icon";
import { fetchBudgetMonth, fetchMonthIncome } from "@/lib/api";
import { euroCents } from "@/lib/format";

/* Late-income nudge (spec: income-schedules, design D9): while an expected
   income of the current month is more than 3 days late, one coach capsule
   offers to add it or to link one that already arrived. Dismissal is a
   per-browser convenience for those occurrences in this month only. */

const dismissKey = (month: string, scheduleIds: string[]) =>
  `olmenta-late-income-dismissed:${month}:${[...scheduleIds].sort().join(",")}`;

function readDismissed(key: string): boolean {
  try {
    return globalThis.localStorage?.getItem(key) === "1";
  } catch {
    return false;
  }
}

function ordinal(day: number): string {
  if (day % 100 >= 11 && day % 100 <= 13) return `${day}th`;
  return `${day}${["th", "st", "nd", "rd"][day % 10] ?? "th"}`;
}

export function LateIncomeNudge({ month }: Readonly<{ month: string }>) {
  const income = useQuery({ queryKey: ["income", month], queryFn: () => fetchMonthIncome(month) });
  const late = (income.data?.occurrences ?? []).filter((o) => o.status === "late");
  const key = dismissKey(month, late.map((o) => o.schedule_id));
  const [dismissedKey, setDismissedKey] = React.useState<string | null>(null);
  const [adding, setAdding] = React.useState(false);
  const [linking, setLinking] = React.useState(false);
  const budget = useQuery({
    queryKey: ["budget", month],
    queryFn: () => fetchBudgetMonth(month),
    enabled: linking,
  });

  const dismissed = dismissedKey === key || readDismissed(key);
  if (late.length === 0 || dismissed) return null;

  const [first] = late;
  const total = late.reduce((t, o) => t + o.amount_cents, 0);
  const message =
    late.length === 1
      ? `Your ${first.name} (${euroCents(first.amount_cents)})${first.day ? ` usually arrives on the ${ordinal(first.day)} and` : ""} isn't here yet`
      : `${late.length} expected incomes (${euroCents(total)}) haven't arrived yet`;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 16 }} data-testid="late-income-nudge">
      <CoachCapsule
        message={message}
        cta="Add it"
        accent="mint"
        onClick={() => setAdding(true)}
        style={{ flex: "1 1 320px", minWidth: 0 }}
      />
      <button
        onClick={() => setLinking(true)}
        style={{
          border: "none",
          background: "transparent",
          cursor: "pointer",
          font: "600 13.5px var(--font-sans)",
          color: "var(--brand)",
          padding: "6px 8px",
        }}
      >
        It&apos;s already here
      </button>
      <button
        aria-label="Dismiss"
        onClick={() => {
          try {
            globalThis.localStorage?.setItem(key, "1");
          } catch {
            // Storage unavailable: dismiss for this visit only.
          }
          setDismissedKey(key);
        }}
        style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-subtle)", padding: 6 }}
      >
        <Icon name="x" size={16} />
      </button>
      <AddTransactionDialog
        open={adding}
        onOpenChange={setAdding}
        prefill={{ kind: "income", amountCents: first.amount_cents, payee: first.payer }}
      />
      {budget.data && (
        <IncomeBreakdown open={linking} onOpenChange={setLinking} view={budget.data} />
      )}
    </div>
  );
}
