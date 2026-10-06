/* Client mirror of backend/app/services/debts.py (debts design D5), for the
   debt editor's live preview. The server stays the source of truth. */

import type { RatePeriod } from "./api";

export const HORIZON_MONTHS = 120;

/** Monthly rate as a fraction; a yearly rate is divided by 12. */
export function monthlyRate(rateBp: number | null, period: RatePeriod | null): number | null {
  if (rateBp == null || (period !== "month" && period !== "year")) return null;
  const rate = rateBp / 10_000;
  return period === "month" ? rate : rate / 12;
}

/** Smallest monthly payment (rounded up to the cent) that pays `owed` off in
    `months` payments, interest included when a rate is known. */
export function planForTarget(owedCents: number, rate: number | null, months: number): number {
  if (owedCents <= 0 || months < 1) return 0;
  if (!rate) return Math.ceil(owedCents / months - 1e-9);
  return Math.ceil((owedCents * rate) / (1 - (1 + rate) ** -months) - 1e-9);
}

/** Payments needed at `monthlyCents` a month, or null when it never ends
    (the payment doesn't beat the interest) within the horizon. */
export function paymentsToPayOff(owedCents: number, rate: number | null, monthlyCents: number): number | null {
  if (owedCents <= 0) return 0;
  if (monthlyCents <= 0) return null;
  let owed = owedCents;
  for (let n = 1; n <= HORIZON_MONTHS; n++) {
    if (rate) owed += owed * rate;
    owed -= monthlyCents;
    if (owed <= 0.5) return n;
  }
  return null;
}

/** "1,5 % a month" / "18 % a year" — never TAE or APR. */
export function rateLabel(rateBp: number | null, period: RatePeriod | null): string {
  if (rateBp == null || !period) return "rate unknown";
  const pct = (rateBp / 100).toLocaleString("es-ES", { maximumFractionDigits: 2 });
  return `${pct} % a ${period}`;
}
