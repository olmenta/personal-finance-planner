"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { accountName, useAccounts } from "@/components/AccountPicker";
import { NO_CATEGORY } from "@/components/CategoryCombobox";
import type { BadgeTone } from "@/components/ui/Badge";
import { fetchPayees, type PayeeOut, type ReviewDecisions, type TwinMatch } from "@/lib/api";
import {
  TRANSFER_PREFIX,
  type MatchDecision,
  type TransactionReviewRowProps,
} from "./TransactionReviewRow";

/** A row to resolve, from either source: a staged import row or a
    confirmed uncategorized transaction. */
export interface ReviewItem {
  row: {
    id: string;
    account_id: string;
    date: string;
    amount_cents: number;
    description: string | null;
    category_id: string | null;
    payee_name: string | null;
    match?: TwinMatch | null;
  };
  /** The suggestion the row starts with: a category id, NO_CATEGORY or "".
      The badge shows while the row keeps it. */
  defaultSelection: string;
  defaultPayee: string;
  badgeLabel?: string | null;
  badgeTone?: BadgeTone;
}

type TransferGroups = NonNullable<TransactionReviewRowProps["transferGroups"]>;

const NO_PAYEES: PayeeOut[] = [];
const NO_TRANSFERS: TransferGroups = [];

/* State and decisions shared by both reviews (unified-transaction-review
   design D4). Per-row edits live in one map per field and are changed
   through dispatchers created once, so a keystroke changes one entry and
   only that row re-renders (TransactionReviewRow is memoized). */
export function useTransactionReview(items: ReviewItem[], enabled = true) {
  const [selections, setSelections] = React.useState<Record<string, string>>({});
  const [payeeEdits, setPayeeEdits] = React.useState<Record<string, string>>({});
  const [noteEdits, setNoteEdits] = React.useState<Record<string, string>>({});
  const [decisions, setDecisions] = React.useState<Record<string, MatchDecision>>({});

  const { data: payees } = useQuery({ queryKey: ["payees"], queryFn: fetchPayees, enabled });
  const { all: allAccounts, active: accounts } = useAccounts(enabled);

  const onSelect = React.useCallback(
    (id: string, value: string) => setSelections((prev) => ({ ...prev, [id]: value })),
    [],
  );
  const onPayee = React.useCallback(
    (id: string, value: string) => setPayeeEdits((prev) => ({ ...prev, [id]: value })),
    [],
  );
  const onNote = React.useCallback(
    (id: string, value: string) => setNoteEdits((prev) => ({ ...prev, [id]: value })),
    [],
  );
  const onDecision = React.useCallback(
    (id: string, value: MatchDecision | null) =>
      setDecisions((prev) => {
        const next = { ...prev };
        if (value === null) delete next[id];
        else next[id] = value;
        return next;
      }),
    [],
  );
  const reset = React.useCallback(() => {
    setSelections({});
    setPayeeEdits({});
    setNoteEdits({});
    setDecisions({});
  }, []);

  // "Transfers →" choices per (row account, direction): the user's other
  // active accounts. Memoized so rows keep stable props.
  const transferGroupsByKey = React.useMemo(() => {
    const byKey = new Map<string, TransferGroups>();
    for (const account of allAccounts) {
      const targets = accounts.filter((a) => a.id !== account.id);
      for (const inflow of [true, false]) {
        byKey.set(
          `${account.id}:${inflow ? "in" : "out"}`,
          targets.length === 0
            ? NO_TRANSFERS
            : [
                {
                  heading: "Transfers →",
                  options: targets.map((a) => ({
                    value: `${TRANSFER_PREFIX}${a.id}`,
                    label: `Transfer ${inflow ? "←" : "→"} ${a.name}`,
                  })),
                },
              ],
        );
      }
    }
    return byKey;
  }, [allAccounts, accounts]);
  const transferGroups = (accountId: string, inflow: boolean): TransferGroups =>
    transferGroupsByKey.get(`${accountId}:${inflow ? "in" : "out"}`) ?? NO_TRANSFERS;

  const selectionOf = (item: ReviewItem) => selections[item.row.id] ?? item.defaultSelection;
  const payeeOf = (item: ReviewItem) => payeeEdits[item.row.id] ?? item.defaultPayee;
  const noteOf = (item: ReviewItem) => noteEdits[item.row.id] ?? item.row.description ?? "";

  function rowProps(item: ReviewItem, last: boolean): TransactionReviewRowProps {
    const { row } = item;
    return {
      row,
      last,
      selection: selectionOf(item),
      payee: payeeOf(item),
      note: noteOf(item),
      payees: payees ?? NO_PAYEES,
      onSelect,
      onPayee,
      onNote,
      // The badge describes the suggestion: shown while the row keeps it.
      badgeLabel:
        item.badgeLabel && item.defaultSelection && selectionOf(item) === item.defaultSelection
          ? item.badgeLabel
          : null,
      badgeTone: item.badgeTone,
      transferGroups: transferGroups(row.account_id, row.amount_cents > 0),
      decision: row.match ? decisions[row.id] : undefined,
      matchAccountName: row.match ? accountName(allAccounts, row.match.other_account_id) : null,
      onDecision,
    };
  }

  /** What to send: only what differs from the stored row (a kept
      suggestion differs from a stored null and is sent). */
  function buildDecisions(): ReviewDecisions {
    const out: ReviewDecisions = {
      overrides: {},
      payee_overrides: {},
      note_overrides: {},
      transfer_overrides: {},
      accept_matches: [],
    };
    for (const item of items) {
      const { row } = item;
      if (row.match && decisions[row.id] === "accept") {
        // The existing twin is adopted; this row is dropped.
        out.accept_matches.push(row.id);
        continue;
      }
      const note = noteOf(item).trim();
      if (note !== (row.description ?? "").trim()) out.note_overrides[row.id] = note || null;
      const picked = selectionOf(item);
      if (picked.startsWith(TRANSFER_PREFIX)) {
        out.transfer_overrides[row.id] = picked.slice(TRANSFER_PREFIX.length);
        continue;
      }
      const pickedId = picked === NO_CATEGORY || picked === "" ? null : picked;
      if (pickedId !== row.category_id) out.overrides[row.id] = pickedId;
      const payee = payeeOf(item).trim();
      if (payee !== (row.payee_name ?? "").trim()) out.payee_overrides[row.id] = payee;
    }
    return out;
  }

  return { rowProps, buildDecisions, reset };
}

export function hasDecisions(d: ReviewDecisions): boolean {
  return (
    Object.keys(d.overrides).length > 0 ||
    Object.keys(d.payee_overrides).length > 0 ||
    Object.keys(d.note_overrides).length > 0 ||
    Object.keys(d.transfer_overrides).length > 0 ||
    d.accept_matches.length > 0
  );
}
