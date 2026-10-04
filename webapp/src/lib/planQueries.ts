import type { QueryClient } from "@tanstack/react-query";

/* Every money write (transaction, assignment, move, schedule) can change the
   budget, the month overview, the projection and the annual plan — refresh
   them all, every month (the write may not be in the month on screen). */
export function invalidateMoneyQueries(queryClient: QueryClient): void {
  for (const key of ["budget", "summary", "overview", "upcoming", "plan-summary"]) {
    queryClient.invalidateQueries({ queryKey: [key] });
  }
}
