import type { QueryClient } from "@tanstack/react-query";

/* Every money write (transaction, transfer, assignment, move, schedule) can
   change the budget, the month overview, the projection, the annual plan,
   the account balances and expected-versus-received income — refresh them
   all, every month (the write may not be in the month on screen). */
export function invalidateMoneyQueries(queryClient: QueryClient): void {
  for (const key of ["budget", "summary", "overview", "upcoming", "plan-summary", "accounts", "income", "debts"]) {
    queryClient.invalidateQueries({ queryKey: [key] });
  }
}

/* Income schedule writes change the plan and the month income views, never
   the budget (principle 1). */
export function invalidateIncomeQueries(queryClient: QueryClient): void {
  for (const key of ["income-schedules", "income", "upcoming", "plan-summary"]) {
    queryClient.invalidateQueries({ queryKey: [key] });
  }
}
