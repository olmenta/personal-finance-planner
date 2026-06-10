/* Demo data mirroring the Olmenta design-system UI kits, adapted to euros.
   Only the dashboard and goals screens still read from here — budget and
   transactions are served by the real API (lib/api.ts). */

import type { ChipTone } from "@/components/ui/IconChip";
import type { BadgeTone } from "@/components/ui/Badge";

export const balance = {
  amount: "87.457",
  cents: ",85 €",
  delta: "784 € than last week",
  income: "4.875,12 €",
  expenses: "8.145,78 €",
};

export interface Txn {
  icon: string;
  tone: ChipTone;
  title: string;
  subtitle: string;
  acct: string;
  cat: string;
  badgeTone: BadgeTone;
  date: string;
  amount: string;
  direction: "in" | "out";
}

export const transactions: Txn[] = [
  { icon: "dollar-sign", tone: "income", title: "Salary", subtitle: "Main account · 10 Jun", acct: "•••• 4821", cat: "Income", badgeTone: "income", date: "10 Jun 2026", amount: "4.875,12 €", direction: "in" },
  { icon: "wallet", tone: "violet", title: "Cash withdrawal", subtitle: "Red Card · 12 Jun", acct: "Red Card", cat: "Transfer", badgeTone: "brand", date: "12 Jun 2026", amount: "354,25 €", direction: "out" },
  { icon: "shopping-bag", tone: "violet", title: "Apple Store", subtitle: "Shopping · 8 Jun", acct: "•••• 0934", cat: "Shopping", badgeTone: "brand", date: "8 Jun 2026", amount: "129,00 €", direction: "out" },
  { icon: "coffee", tone: "info", title: "Blue Bottle Coffee", subtitle: "Food & dining · 9 Jun", acct: "•••• 0934", cat: "Food", badgeTone: "info", date: "9 Jun 2026", amount: "12,49 €", direction: "out" },
  { icon: "plane", tone: "warning", title: "Iberia", subtitle: "Travel · 5 Jun", acct: "•••• 0934", cat: "Travel", badgeTone: "warning", date: "5 Jun 2026", amount: "642,00 €", direction: "out" },
  { icon: "receipt", tone: "mint", title: "Iberdrola", subtitle: "Auto-pay · 3 Jun", acct: "Auto-pay", cat: "Bills", badgeTone: "mint", date: "3 Jun 2026", amount: "214,30 €", direction: "out" },
];

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

export const weeks = [
  { l: "W1", a: 62, b: 38 },
  { l: "W2", a: 80, b: 52 },
  { l: "W3", a: 48, b: 30 },
  { l: "W4", a: 92, b: 60 },
  { l: "W5", a: 70, b: 44 },
];

export const goals = [
  { icon: "plane", tone: "violet" as ChipTone, label: "Japan trip", saved: "3.400 €", target: "5.000 €", percent: 68, due: "Oct 2026" },
  { icon: "piggy-bank", tone: "mint" as ChipTone, label: "Emergency fund", saved: "9.000 €", target: "12.000 €", percent: 75, due: "Ongoing" },
  { icon: "credit-card", tone: "info" as ChipTone, label: "New laptop", saved: "640 €", target: "2.200 €", percent: 29, due: "Aug 2026" },
];
