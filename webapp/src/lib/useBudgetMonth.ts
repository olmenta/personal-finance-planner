"use client";

import React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  confirmSuggestions as confirmSuggestionsApi,
  currentMonth,
  fetchBudgetMonth,
  putAssignment,
  type BudgetCategoryView,
  type BudgetMonthView,
} from "./api";

/* Server state over GET /api/budget/{month} (design D3): same public shape
   as the old mock hook, queries/mutations inside. Assign is optimistic with
   rollback; the server view always wins on settle. */

export function availableCents(c: BudgetCategoryView): number {
  return c.assigned_cents + c.rollover_cents - c.spent_cents;
}

function patchAssignment(
  view: BudgetMonthView,
  categoryId: string,
  amountCents: number,
): BudgetMonthView {
  let delta = 0;
  const groups = view.groups.map((g) => ({
    ...g,
    categories: g.categories.map((c) => {
      if (c.id !== categoryId) return c;
      delta = amountCents - c.assigned_cents;
      return {
        ...c,
        assigned_cents: amountCents,
        available_cents: c.available_cents + (amountCents - c.assigned_cents),
        suggestion_state: "edited" as const,
      };
    }),
  }));
  return {
    ...view,
    groups,
    to_be_assigned_cents: view.to_be_assigned_cents - delta,
  };
}

export function useBudgetMonth() {
  const month = currentMonth();
  const queryClient = useQueryClient();
  const queryKey = ["budget", month];

  const query = useQuery({
    queryKey,
    queryFn: () => fetchBudgetMonth(month),
  });

  const assignMutation = useMutation({
    mutationFn: ({ categoryId, amountCents }: { categoryId: string; amountCents: number }) =>
      putAssignment(month, categoryId, amountCents),
    onMutate: async ({ categoryId, amountCents }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<BudgetMonthView>(queryKey);
      if (previous) {
        queryClient.setQueryData(queryKey, patchAssignment(previous, categoryId, amountCents));
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const confirmMutation = useMutation({
    mutationFn: (categoryIds: string[]) => confirmSuggestionsApi(month, categoryIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const data = query.data;
  const allCategories = React.useMemo(
    () => data?.groups.flatMap((g) => g.categories) ?? [],
    [data],
  );

  const draftIds = allCategories
    .filter((c) => c.suggestion_state === "draft")
    .map((c) => c.id);
  /* First month: no history anywhere → empty state (spec: budget-suggestions). */
  const isFirstMonth =
    allCategories.length > 0 && allCategories.every((c) => c.suggestion_cents === null);

  const assign = (categoryId: string, amountCents: number) =>
    assignMutation.mutate({ categoryId, amountCents });

  const confirmSuggestions = (categoryIds: string[]) =>
    confirmMutation.mutate(categoryIds);

  return {
    month: data,
    toBeAssignedCents: data?.to_be_assigned_cents ?? 0,
    draftIds,
    isFirstMonth,
    assign,
    confirmSuggestions,
    isLoading: query.isPending,
    isError: query.isError,
    refetch: query.refetch,
    assignFailed: assignMutation.isError,
    retryAssign: () => {
      assignMutation.reset();
      if (assignMutation.variables) assignMutation.mutate(assignMutation.variables);
    },
  };
}
