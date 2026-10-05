"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import { Separator } from "@/components/shadcn/separator";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CategoryCombobox, NO_CATEGORY } from "@/components/CategoryCombobox";
import {
  applyCategories,
  fetchTransactions,
  type CategoryAssignment,
  type CategoryProposal,
  type SuggestionConfidence,
  type TransactionOut,
} from "@/lib/api";
import { euroCents } from "@/lib/format";
import { invalidateMoneyQueries } from "@/lib/planQueries";

const CONFIDENCE_ORDER: Record<SuggestionConfidence, number> = {
  low: 0,
  medium: 1,
  high: 2,
};

const CONFIDENCE_TONE: Record<SuggestionConfidence, BadgeTone> = {
  high: "mint",
  medium: "neutral",
  low: "warning",
};

interface RowState {
  checked: boolean;
  categoryId: string;
  payee: string;
}

export interface SuggestCategoriesDialogProps {
  proposals: CategoryProposal[] | null; // null = closed; [] = empty state
  onClose: () => void;
}

export function SuggestCategoriesDialog({
  proposals,
  onClose,
}: SuggestCategoriesDialogProps) {
  return (
    <Dialog open={proposals !== null} onOpenChange={(o) => !o && onClose()}>
      {proposals !== null && (
        <ReviewContent proposals={proposals} onClose={onClose} />
      )}
    </Dialog>
  );
}

function ReviewContent({
  proposals,
  onClose,
}: Readonly<{ proposals: CategoryProposal[]; onClose: () => void }>) {
  const queryClient = useQueryClient();
  // Proposals can span months — fetch the full confirmed list for row details.
  const { data: allTransactions } = useQuery({
    queryKey: ["transactions"],
    queryFn: () => fetchTransactions(),
  });

  const transactionsById = React.useMemo(() => {
    const map = new Map<string, TransactionOut>();
    for (const t of allTransactions ?? []) map.set(t.id, t);
    return map;
  }, [allTransactions]);

  // Low confidence first — attention lands where the model is unsure (D5).
  const ordered = React.useMemo(
    () =>
      [...proposals].sort(
        (a, b) => CONFIDENCE_ORDER[a.confidence] - CONFIDENCE_ORDER[b.confidence],
      ),
    [proposals],
  );

  const [rows, setRows] = React.useState<Record<string, RowState>>(() =>
    Object.fromEntries(
      proposals.map((p) => [
        p.transaction_id,
        { checked: true, categoryId: p.category_id ?? "", payee: p.payee ?? "" },
      ]),
    ),
  );

  const setRow = (id: string, patch: Partial<RowState>) =>
    setRows((r) => ({ ...r, [id]: { ...r[id], ...patch } }));

  const checkedCount = Object.values(rows).filter((r) => r.checked).length;

  const mutation = useMutation({
    mutationFn: () => {
      const assignments: Record<string, CategoryAssignment> = {};
      for (const [id, row] of Object.entries(rows)) {
        if (!row.checked) continue;
        const assignment: CategoryAssignment = {};
        if (row.categoryId === NO_CATEGORY) {
          // "Ready to assign" / "Uncategorized": clear a stored category so
          // an inflow counts as income again; already-empty rows stay as is.
          if (transactionsById.get(id)?.category_id) assignment.category_id = null;
        } else if (row.categoryId) {
          assignment.category_id = row.categoryId;
        }
        // Clearing payees is not this dialog's job — only send real names.
        if (row.payee.trim()) assignment.payee = row.payee.trim();
        if (assignment.category_id !== undefined || assignment.payee) assignments[id] = assignment;
      }
      return applyCategories(assignments);
    },
    onSuccess: () => {
      const months = new Set(
        Object.entries(rows)
          .filter(([, r]) => r.checked)
          .map(([id]) => transactionsById.get(id)?.date.slice(0, 7))
          .filter(Boolean) as string[],
      );
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      for (const m of months) {
        queryClient.invalidateQueries({ queryKey: ["budget", m] });
        queryClient.invalidateQueries({ queryKey: ["summary", m] });
      }
      // Later months' To Be Assigned, the overview and the plan move too.
      invalidateMoneyQueries(queryClient);
      onClose();
    },
  });

  return (
    <DialogContent
      className="p-0 gap-0 overflow-hidden"
      style={{
        borderRadius: "var(--r-2xl)",
        maxWidth: 720,
        border: "1px solid var(--border-hairline)",
        boxShadow: "var(--shadow-xl)",
      }}
    >
      <DialogHeader
        style={{
          padding: "22px 24px 14px",
          borderBottom: "1px solid var(--border-hairline)",
        }}
      >
        <DialogTitle
          style={{
            font: "700 19px var(--font-sans)",
            letterSpacing: "-0.4px",
            color: "var(--text-strong)",
          }}
        >
          Review suggested categories
        </DialogTitle>
      </DialogHeader>

      <div style={{ maxHeight: "55vh", overflowY: "auto", padding: "8px 24px" }}>
        {ordered.length === 0 ? (
          <div style={{ textAlign: "center", padding: "36px 0" }}>
            <div
              style={{
                font: "700 16px var(--font-sans)",
                color: "var(--text-strong)",
                letterSpacing: "-0.2px",
              }}
            >
              Nothing to suggest right now
            </div>
            <div
              style={{
                font: "500 13.5px var(--font-sans)",
                color: "var(--text-muted)",
                marginTop: 6,
              }}
            >
              Every transaction may already be categorized, or suggestions are
              briefly unavailable — you can still set each category by hand
              from the Transactions screen (Edit on the row).
            </div>
          </div>
        ) : (
          ordered.map((proposal, i) => {
            const txn = transactionsById.get(proposal.transaction_id);
            const row = rows[proposal.transaction_id];
            if (!row) return null;
            const isIncome = (txn?.amount_cents ?? 0) > 0;
            return (
              <div
                key={proposal.transaction_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "20px 1.6fr 1fr 1fr auto",
                  gap: 12,
                  alignItems: "center",
                  padding: "12px 0",
                  borderBottom:
                    i < ordered.length - 1 ? "1px solid var(--border-hairline)" : "none",
                  opacity: row.checked ? 1 : 0.55,
                }}
              >
                <input
                  type="checkbox"
                  checked={row.checked}
                  onChange={(e) =>
                    setRow(proposal.transaction_id, { checked: e.target.checked })
                  }
                  aria-label="Include this transaction"
                  style={{ width: 16, height: 16, accentColor: "var(--brand)" }}
                />
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      font: "600 13.5px var(--font-sans)",
                      color: "var(--text-strong)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {txn?.description ?? "Transaction"}
                  </div>
                  <div
                    style={{
                      font: "500 12px var(--font-sans)",
                      color: isIncome ? "var(--income)" : "var(--text-muted)",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {txn ? `${txn.date} · ${isIncome ? "+" : "−"}${euroCents(Math.abs(txn.amount_cents))}` : ""}
                  </div>
                </div>
                <input
                  value={row.payee}
                  placeholder="Payee"
                  maxLength={120}
                  aria-label="Payee"
                  onChange={(e) =>
                    setRow(proposal.transaction_id, { payee: e.target.value })
                  }
                  style={{
                    height: 36,
                    padding: "0 10px",
                    borderRadius: "var(--r-sm)",
                    border: "1.5px solid var(--border-hairline)",
                    background: "var(--surface)",
                    font: "500 13px var(--font-sans)",
                    color: "var(--text-strong)",
                    minWidth: 0,
                  }}
                />
                <CategoryCombobox
                  size="sm"
                  // An inflow the AI left without a category is income:
                  // "Ready to assign" until the user picks a category.
                  value={row.categoryId || (isIncome ? NO_CATEGORY : "")}
                  noneLabel={isIncome ? "Ready to assign" : "Uncategorized"}
                  placeholder="Pick category"
                  onChange={(v) => setRow(proposal.transaction_id, { categoryId: v })}
                />
                <Badge tone={CONFIDENCE_TONE[proposal.confidence]}>
                  {proposal.confidence}
                </Badge>
              </div>
            );
          })
        )}

        {mutation.isError && (
          <div
            role="alert"
            style={{
              margin: "10px 0",
              font: "600 13px var(--font-sans)",
              color: "var(--expense)",
              background: "var(--expense-soft)",
              borderRadius: "var(--r-md)",
              padding: "9px 12px",
            }}
          >
            That didn&apos;t apply — check the backend is running and try again.
          </div>
        )}
      </div>

      <Separator style={{ background: "var(--border-hairline)" }} />

      <div
        style={{
          padding: "16px 24px",
          display: "flex",
          justifyContent: "flex-end",
          gap: 10,
        }}
      >
        <Button variant="ghost" size="sm" type="button" onClick={onClose}>
          Cancel
        </Button>
        {ordered.length > 0 && (
          <Button
            variant="primary"
            size="sm"
            type="button"
            disabled={checkedCount === 0 || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {`Apply ${checkedCount} ${checkedCount === 1 ? "category" : "categories"}`}
          </Button>
        )}
      </div>
    </DialogContent>
  );
}
