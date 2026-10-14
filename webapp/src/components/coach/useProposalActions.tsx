"use client";

import { useRouter } from "next/navigation";
import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import { IncomeBreakdown } from "@/components/budget/IncomeBreakdown";
import {
  acceptProposal,
  currentMonth,
  dismissProposal,
  fetchBudgetMonth,
  type CoachProposal,
} from "@/lib/api";
import { invalidateMoneyQueries } from "@/lib/planQueries";

/* The actions of a coach proposal (coach-proposals design D5): one-tap raise
   and lower go to the API; adding or linking income and opening a screen
   stay in the browser. Shared by the feed card and the dashboard capsule. */

export interface ProposalAction {
  label: string;
  run: () => void;
  pending?: boolean;
}

const OPEN_LABEL: Partial<Record<CoachProposal["kind"], string>> = {
  late_debt_payment: "See my plan",
  short_months: "See the month",
  unassigned: "Give it a job",
};

export function useProposalActions(p: CoachProposal) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [adding, setAdding] = React.useState(false);
  const [linking, setLinking] = React.useState(false);
  const [pickingSource, setPickingSource] = React.useState(false);
  const month = currentMonth();
  const budget = useQuery({
    queryKey: ["budget", month],
    queryFn: () => fetchBudgetMonth(month),
    enabled: linking,
  });

  const refresh = () => {
    invalidateMoneyQueries(queryClient);
    queryClient.invalidateQueries({ queryKey: ["coach-proposals"] });
  };
  const accept = useMutation({
    mutationFn: (from?: string) => acceptProposal(p.fingerprint, from),
    onSuccess: refresh,
  });
  const dismiss = useMutation({
    mutationFn: () => dismissProposal(p.fingerprint),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["coach-proposals"] }),
  });

  let primary: ProposalAction | null = null;
  let secondary: ProposalAction | null = null;
  if (p.action === "raise") {
    primary = p.sources?.length
      ? { label: "Raise it", run: () => setPickingSource(true) }
      : { label: "Raise it", run: () => accept.mutate(undefined), pending: accept.isPending };
  } else if (p.action === "lower") {
    primary = { label: "Lower it", run: () => accept.mutate(undefined), pending: accept.isPending };
  } else if (p.action === "add_income") {
    primary = { label: "Add it", run: () => setAdding(true) };
    secondary = { label: "It's already here", run: () => setLinking(true) };
  } else if (p.action === "link_income") {
    primary = { label: "It's already here", run: () => setLinking(true) };
  } else if (p.href) {
    const href = p.href;
    primary = { label: OPEN_LABEL[p.kind] ?? "Open", run: () => router.push(href) };
  }
  const notNow: ProposalAction = { label: "Not now", run: () => dismiss.mutate(), pending: dismiss.isPending };

  const sources = pickingSource && p.sources?.length ? p.sources : null;
  const takeFrom = (categoryId: string) => accept.mutate(categoryId);
  const error = accept.isError ? "That didn't go through — try again." : null;

  const dialogs = (
    <>
      {p.action === "add_income" && (
        <AddTransactionDialog
          open={adding}
          onOpenChange={(o) => {
            setAdding(o);
            if (!o) refresh();
          }}
          prefill={{ kind: "income", amountCents: p.amount_cents, payee: p.payer }}
        />
      )}
      {budget.data && (
        <IncomeBreakdown
          open={linking}
          onOpenChange={(o) => {
            setLinking(o);
            if (!o) refresh();
          }}
          view={budget.data}
        />
      )}
    </>
  );

  return { primary, secondary, notNow, sources, takeFrom, error, dialogs };
}
