"use client";

import React from "react";
import { currentMonth } from "./api";

/* The month every screen shows, chosen in the TopBar selector. Defaults to
   the calendar month; budget, dashboard and transactions all read it. */

type SelectedMonth = [month: string, setMonth: (month: string) => void];

const SelectedMonthContext = React.createContext<SelectedMonth | null>(null);

export function SelectedMonthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [month, setMonth] = React.useState(currentMonth);
  const value = React.useMemo<SelectedMonth>(() => [month, setMonth], [month]);
  return <SelectedMonthContext.Provider value={value}>{children}</SelectedMonthContext.Provider>;
}

export function useSelectedMonth(): SelectedMonth {
  const value = React.useContext(SelectedMonthContext);
  if (!value) throw new Error("useSelectedMonth outside SelectedMonthProvider");
  return value;
}

/** Selector options: the next 3 months, the current one, and 12 back. */
export function monthOptions(): { value: string; label: string }[] {
  const now = new Date();
  return Array.from({ length: 16 }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() + 3 - i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
    return { value, label };
  });
}
