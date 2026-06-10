/* Demo data mirroring the Olmenta design-system UI kits, adapted to euros.
   Only the goals screen and the budgets report mode still read from here —
   dashboard, budget assignment and transactions are served by the real API
   (lib/api.ts). */

import type { ChipTone } from "@/components/ui/IconChip";

export interface BudgetCat {
  icon: string;
  tone: ChipTone;
  label: string;
  spent: string;
  limit: string;
  percent: number;
}

export const budgets: BudgetCat[] = [
  { icon: "shopping-bag", tone: "violet", label: "Shopping", spent: "1.305 €", limit: "1.500 €", percent: 87 },
  { icon: "receipt", tone: "info", label: "Bills & utilities", spent: "1.010 €", limit: "1.000 €", percent: 101 },
  { icon: "coffee", tone: "mint", label: "Food & dining", spent: "884 €", limit: "1.200 €", percent: 74 },
  { icon: "plane", tone: "warning", label: "Travel", spent: "589 €", limit: "800 €", percent: 74 },
];

export const chartLegend: [string, string][] = [
  ["var(--chart-1)", "Shopping 31%"],
  ["var(--chart-3)", "Bills 24%"],
  ["var(--chart-2)", "Food 21%"],
  ["var(--chart-4)", "Travel 14%"],
  ["var(--chart-empty)", "Other 10%"],
];

export const goals = [
  { icon: "plane", tone: "violet" as ChipTone, label: "Japan trip", saved: "3.400 €", target: "5.000 €", percent: 68, due: "Oct 2026" },
  { icon: "piggy-bank", tone: "mint" as ChipTone, label: "Emergency fund", saved: "9.000 €", target: "12.000 €", percent: 75, due: "Ongoing" },
  { icon: "credit-card", tone: "info" as ChipTone, label: "New laptop", saved: "640 €", target: "2.200 €", percent: 29, due: "Aug 2026" },
];
