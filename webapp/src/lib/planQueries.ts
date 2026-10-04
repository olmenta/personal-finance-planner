import type { QueryClient } from "@tanstack/react-query";

/* Every money write (transaction, transfer, assignment, move, schedule) can
   change the budget, the month overview, the projection, the annual plan and
   the account balances — refresh them all, every month (the write may not be
   in the month on screen). */
export function invalidateMoneyQueries(queryClient: QueryClient): void {
  for (const key of ["budget", "summary", "overview", "upcoming", "plan-summary", "accounts"]) {
    queryClient.invalidateQueries({ queryKey: [key] });
  }
}
