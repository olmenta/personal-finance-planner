"use client";

import Link from "next/link";
import React from "react";
import { useQuery } from "@tanstack/react-query";
import { CoachCapsule } from "@/components/ui/CoachCapsule";
import { Icon } from "@/components/ui/Icon";
import { fetchOverview } from "@/lib/api";
import { euroCents } from "@/lib/format";

/* Late debt payment nudge (spec: debts, design D7): while a required debt
   payment of the current month is more than 3 days past its day, one coach
   capsule names it and links to "What you owe". Dismissal is per browser,
   for those payments in this month only. */

const dismissKey = (month: string, scheduleIds: string[]) =>
  `olmenta-late-debt-dismissed:${month}:${[...scheduleIds].sort().join(",")}`;

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

export function LateDebtNudge({ month }: Readonly<{ month: string }>) {
  const overview = useQuery({ queryKey: ["overview", month], queryFn: () => fetchOverview(month) });
  const late = (overview.data?.to_pay ?? []).filter((p) => p.late);
  const key = dismissKey(month, late.map((p) => p.schedule_id));
  const [dismissedKey, setDismissedKey] = React.useState<string | null>(null);

  if (late.length === 0 || dismissedKey === key || readDismissed(key)) return null;

  const [first] = late;
  const total = late.reduce((t, p) => t + p.amount_cents, 0);
  const message =
    late.length === 1
      ? `Your ${first.category_name} payment${first.day ? ` was due on the ${ordinal(first.day)} and` : ""} hasn't gone out yet`
      : `${late.length} debt payments (${euroCents(total)}) are late`;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }} data-testid="late-debt-nudge">
      <Link href="/debts" style={{ flex: "1 1 320px", minWidth: 0, textDecoration: "none" }}>
        <CoachCapsule message={message} cta="See my plan" accent="violet" />
      </Link>
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
    </div>
  );
}
