/* Client mirror of backend/app/services/schedules.py, for the schedule
   editor's live preview (category-targets design D3/D8). The server stays
   the source of truth: everything saved is re-read from the API. */

import type { ScheduleIn, ScheduleOut, SchedulePattern } from "./api";
import { euroCents } from "./format";

type ScheduleLike = ScheduleIn | ScheduleOut;

export const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
export const MONTH_SHORT = MONTH_NAMES.map((m) => m.slice(0, 3));

export const PATTERNS: { value: SchedulePattern; label: string }[] = [
  { value: "monthly", label: "Every month" },
  { value: "some_months", label: "Some months" },
  { value: "annual", label: "Once a year" },
  { value: "every_n", label: "Every N months" },
  { value: "once", label: "One payment on a date" },
  { value: "no_date", label: "No date (goal)" },
];

export const monthIndex = (month: string) => {
  const [y, m] = month.split("-").map(Number);
  return y * 12 + m - 1;
};
export const monthFromIndex = (i: number) =>
  `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`;
export const monthLabel = (month: string) => {
  const [y, m] = month.split("-").map(Number);
  return `${MONTH_NAMES[m - 1]} ${y}`;
};

export function occurs(s: ScheduleLike, month: string): boolean {
  const m = monthIndex(month);
  const mon = (m % 12) + 1;
  switch (s.pattern) {
    case "monthly": {
      if (s.count == null) return true;
      const start = monthIndex(s.start_month ?? month);
      return m >= start && m < start + s.count;
    }
    case "some_months":
      return (s.months ?? []).includes(mon);
    case "annual":
      return mon === s.month;
    case "every_n": {
      const start = monthIndex(s.start_month ?? month);
      return m >= start && (m - start) % (s.every_n ?? 1) === 0;
    }
    case "once":
      return s.once_month === month;
    default:
      return false;
  }
}

export function normalAmount(s: ScheduleLike, month: string): number {
  const a = s.amount_cents;
  switch (s.pattern) {
    case "monthly":
      return s.count == null || occurs(s, month) ? a : 0;
    case "some_months":
      return (a * (s.months ?? []).length) / 12;
    case "annual":
    case "no_date":
      return a / 12;
    case "every_n":
      return a / (s.every_n ?? 1);
    default:
      return 0;
  }
}

export const paymentsIn = (list: ScheduleLike[], month: string) =>
  list.reduce((t, s) => t + (occurs(s, month) ? s.amount_cents : 0), 0);

export const categoryNormal = (list: ScheduleLike[], month: string) =>
  list.reduce((t, s) => t + normalAmount(s, month), 0);

export function catchUp(list: ScheduleLike[], month: string, saved: number): number {
  const start = monthIndex(month);
  let cumulative = 0;
  let best = 0;
  for (let j = start; j < start + 12; j++) {
    cumulative += paymentsIn(list, monthFromIndex(j));
    if (cumulative > 0) best = Math.max(best, (cumulative - saved) / (j - start + 1));
  }
  return Math.max(0, best);
}

/** 12-month projected balance: with the normal amount, and with the
    suggested (max of normal and catch-up, recomputed each month). */
export function balanceProjection(list: ScheduleLike[], month: string, saved: number) {
  const start = monthIndex(month);
  let normal = saved;
  let suggested = saved;
  return Array.from({ length: 12 }, (_, k) => {
    const m = monthFromIndex(start + k);
    const pay = paymentsIn(list, m);
    normal += categoryNormal(list, m) - pay;
    suggested += Math.max(categoryNormal(list, m), catchUp(list, m, suggested)) - pay;
    return { month: m, payment: pay, normal, suggested };
  });
}

function monthsText(months: number[]): string {
  const set = new Set(months);
  if (set.size === 12) return "every month";
  const start = months.find((x) => !set.has(((x + 10) % 12) + 1));
  if (start !== undefined) {
    let end = start;
    let n = 1;
    while (set.has((end % 12) + 1) && n < set.size) {
      end = (end % 12) + 1;
      n++;
    }
    if (n === set.size) {
      return set.size === 1
        ? `in ${MONTH_NAMES[start - 1]}`
        : `from ${MONTH_NAMES[start - 1]} to ${MONTH_NAMES[end - 1]}`;
    }
  }
  return `in ${[...months].sort((a, b) => a - b).map((x) => MONTH_SHORT[x - 1]).join(", ")}`;
}

/** "632,00 € from September to June, day 5" */
export function describe(s: ScheduleLike): string {
  const a = euroCents(s.amount_cents);
  const day = s.day ? `, day ${s.day}` : "";
  let text: string;
  switch (s.pattern) {
    case "monthly":
      text = `${a} every month${day}${s.count ? ` · ${s.count} payments from ${monthLabel(s.start_month ?? "")}` : ""}`;
      break;
    case "some_months":
      text = `${a} ${monthsText(s.months ?? [])}${day}`;
      break;
    case "annual":
      text = `${a} once a year, in ${MONTH_NAMES[(s.month ?? 1) - 1]}${day}`;
      break;
    case "every_n":
      text = `${a} every ${s.every_n} months from ${monthLabel(s.start_month ?? "")}${day}`;
      break;
    case "once":
      text = `${a} once, in ${monthLabel(s.once_month ?? "")}${day}`;
      break;
    default:
      text = `${a} a year, no fixed date`;
  }
  return text + (s.estimated ? " (estimated)" : "");
}
