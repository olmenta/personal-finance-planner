/** Money formatting — euros, Spanish locale (project launches in Spain). */
export function money(n: number, dp = 2): string {
  return n.toLocaleString("es-ES", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
}

/** Formatted amount with the euro sign, e.g. "4.212,34 €". */
export function euro(n: number, dp = 2): string {
  return `${money(n, dp)} €`;
}

/** Integer cents → "4.212,34 €". Amounts are stored as cents (project §6.4). */
export function euroCents(cents: number, dp = 2): string {
  return euro(cents / 100, dp);
}

/** Integer cents → BalanceCard's split parts: 87457 → ["874", ",57 €"]. */
export function splitEuro(cents: number): [string, string] {
  const formatted = euroCents(cents); // "874,57 €"
  const comma = formatted.lastIndexOf(",");
  return [formatted.slice(0, comma), formatted.slice(comma)];
}

/** Parse es-ES user input ("1.234,56", "1234,56", "1234.56", "850") → cents. */
export function parseEuroToCents(input: string): number | null {
  const cleaned = input.replaceAll(/[€\s]/g, "");
  if (!cleaned) return null;
  let normalized: string;
  if (cleaned.includes(",")) {
    normalized = cleaned.replaceAll(".", "").replace(",", ".");
  } else {
    normalized = cleaned;
  }
  const value = Number(normalized);
  if (Number.isNaN(value) || value < 0) return null;
  return Math.round(value * 100);
}
