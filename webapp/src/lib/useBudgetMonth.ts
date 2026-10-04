"use client";

import React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ApiError,
  confirmSuggestions as confirmSuggestionsApi,
  fetchBudgetMonth,
  moveMoney,
  putAssignment,
  type BudgetCategoryView,
  type BudgetMonthView,
  type MoveRequest,
} from "./api";
import { invalidateMoneyQueries } from "./planQueries";
import { useSelectedMonth } from "./selectedMonth";

/* Server state over GET /api/budget/{month} (design D3): same public shape
   as the old mock hook, queries/mutations inside. Assign is optimistic with
   rollback; the server view always wins on settle. */

/* Server-derived: a card's payment category also holds the funded moves from
   budgeted card spending, so assigned + rollover − spent is not enough. The
   optimistic patches keep available_cents in step. */
export function availableCents(c: BudgetCategoryView): number {
  return c.available_cents;
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

/* Optimistic move: source down, target up (or To Be Assigned down when the
   source is null). The server view replaces this on success. */
function patchMove(view: BudgetMonthView, move: MoveRequest): BudgetMonthView {
  const shift = (c: BudgetCategoryView, delta: number): BudgetCategoryView => {
    const available = c.available_cents + delta;
    return {
      ...c,
      assigned_cents: c.assigned_cents + delta,
      available_cents: available,
      overspent_cents: Math.max(0, -available),
      cover_suggestion: available < 0 ? c.cover_suggestion : null,
      suggestion_state: "edited",
    };
  };
  return {
    ...view,
    to_be_assigned_cents:
      move.from_category_id === null
        ? view.to_be_assigned_cents - move.amount_cents
        : view.to_be_assigned_cents,
    groups: view.groups.map((g) => ({
      ...g,
      categories: g.categories.map((c) => {
        if (c.id === move.to_category_id) return shift(c, move.amount_cents);
        if (c.id === move.from_category_id) return shift(c, -move.amount_cents);
        return c;
      }),
    })),
  };
}

/* Move money within a month (budget-rules): shared by the budget screen and
   the post-save cover prompt, so both update the same cached month. */
export function useMoveMoney(month: string) {
  const queryClient = useQueryClient();
  const queryKey = ["budget", month];
  const mutation = useMutation({
    mutationFn: (move: MoveRequest) => moveMoney(month, move),
    onMutate: async (move) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<BudgetMonthView>(queryKey);
      if (previous) queryClient.setQueryData(queryKey, patchMove(previous, move));
      return { previous };
    },
    onSuccess: (view) => {
      queryClient.setQueryData(queryKey, view);
      invalidateMoneyQueries(queryClient);
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
    },
  });
  return {
    move: (body: MoveRequest) => mutation.mutate(body),
    moveFailed: mutation.isError,
    moveErrorCode: mutation.error instanceof ApiError ? mutation.error.code : null,
    retryMove: () => {
      const vars = mutation.variables;
      mutation.reset();
      if (vars) mutation.mutate(vars);
    },
    dismissMoveError: () => mutation.reset(),
  };
}

export function useBudgetMonth() {
  const [month] = useSelectedMonth();
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
    onSettled: () => invalidateMoneyQueries(queryClient),
  });

  const moveMoneyState = useMoveMoney(month);

  const confirmMutation = useMutation({
    mutationFn: (categoryIds: string[]) => confirmSuggestionsApi(month, categoryIds),
    onSuccess: () => invalidateMoneyQueries(queryClient),
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
    ...moveMoneyState,
    assignFailed: assignMutation.isError,
    retryAssign: () => {
      assignMutation.reset();
      if (assignMutation.variables) assignMutation.mutate(assignMutation.variables);
    },
  };
}
