"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/shadcn/dialog";
import { Separator } from "@/components/shadcn/separator";
import { NO_CATEGORY } from "@/components/CategoryCombobox";
import type { BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { applyReview, fetchReview, type SuggestionConfidence } from "@/lib/api";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { TransactionReview } from "./TransactionReview";
import { hasDecisions, useTransactionReview, type ReviewItem } from "./useTransactionReview";

// Low confidence first — attention lands where the model is unsure; rows
// without a suggestion follow.
const CONFIDENCE_ORDER: Record<SuggestionConfidence, number> = { low: 0, medium: 1, high: 2 };
const CONFIDENCE_TONE: Record<SuggestionConfidence, BadgeTone> = {
  high: "mint",
  medium: "neutral",
  low: "warning",
};

export interface CategorizationReviewDialogProps {
  open: boolean;
  onClose: () => void;
}

/* Every uncategorized transaction, resolved with the same review the import
   uses (spec: transaction-review). The AI's category and payee are defaults
   — nothing is written until "Apply changes". */
export function CategorizationReviewDialog({ open, onClose }: CategorizationReviewDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      {open && <ReviewContent onClose={onClose} />}
    </Dialog>
  );
}

function ReviewContent({ onClose }: Readonly<{ onClose: () => void }>) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["transactions-review"],
    queryFn: fetchReview,
    // One AI call per opening: fresh every time, never on focus.
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });

  const items = React.useMemo<ReviewItem[]>(() => {
    const rows = query.data?.transactions ?? [];
    const rank = (c: SuggestionConfidence | null) => (c ? CONFIDENCE_ORDER[c] : 3);
    return [...rows]
      .sort((a, b) => rank(a.confidence) - rank(b.confidence))
      .map((t) => ({
        row: t,
        defaultSelection: t.suggested_category_id ?? NO_CATEGORY,
        defaultPayee: t.suggested_payee ?? t.payee_name ?? "",
        badgeLabel: t.suggested_category_id ? t.confidence : null,
        badgeTone: t.confidence ? CONFIDENCE_TONE[t.confidence] : undefined,
      }));
  }, [query.data]);
  const review = useTransactionReview(items);
  const decisions = review.buildDecisions();
  const changed = hasDecisions(decisions);

  const mutation = useMutation({
    mutationFn: () => applyReview(review.buildDecisions()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      // Budget, summary, overview, plan and account balances, every month.
      invalidateMoneyQueries(queryClient);
      onClose();
    },
  });

  let body: React.ReactNode;
  if (query.isPending) {
    body = <Notice title="Suggesting categories…" text="Reading your uncategorized transactions." />;
  } else if (query.isError) {
    body = (
      <Notice
        title="We couldn't load the review"
        text="Check the backend is running and try again."
        action={
          <Button variant="secondary" size="sm" iconLeft="rotate-cw" onClick={() => query.refetch()}>
            Retry
          </Button>
        }
      />
    );
  } else {
    body = (
      <TransactionReview
        items={items}
        review={review}
        maxHeight="60vh"
        empty={
          <Notice
            title="Nothing to categorize"
            text="Every transaction has a category — new ones will show up here."
          />
        }
      />
    );
  }

  return (
    <DialogContent
      className="p-0 gap-0 overflow-hidden"
      style={{
        borderRadius: "var(--r-2xl)",
        // Same width as the import review: the same rows.
        maxWidth: "max(75vw, 360px)",
        border: "1px solid var(--border-hairline)",
        boxShadow: "var(--shadow-xl)",
      }}
    >
      <DialogHeader style={{ padding: "22px 24px 18px", borderBottom: "1px solid var(--border-hairline)" }}>
        <DialogTitle
          style={{
            font: "700 19px var(--font-sans)",
            letterSpacing: "-0.4px",
            color: "var(--text-strong)",
          }}
        >
          Review uncategorized
        </DialogTitle>
        {items.length > 0 && (
          <p style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-muted)", margin: "4px 0 0" }}>
            {items.length} {items.length === 1 ? "transaction needs" : "transactions need"} a
            category. Pick one, mark a transfer, or link a matching transfer — rows you
            leave as they are stay untouched.
          </p>
        )}
      </DialogHeader>

      <div style={{ padding: "16px 24px 20px" }}>
        {body}
        {mutation.isError && (
          <div
            role="alert"
            style={{
              marginTop: 12,
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

      <div style={{ padding: "16px 24px", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <Button variant="ghost" size="sm" type="button" onClick={onClose}>
          Cancel
        </Button>
        {items.length > 0 && (
          <Button
            variant="primary"
            size="sm"
            type="button"
            iconLeft="check"
            disabled={!changed || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Applying…" : "Apply changes"}
          </Button>
        )}
      </div>
    </DialogContent>
  );
}

function Notice({
  title,
  text,
  action,
}: Readonly<{ title: string; text: string; action?: React.ReactNode }>) {
  return (
    <div style={{ textAlign: "center", padding: "36px 16px" }}>
      <div
        style={{
          font: "700 16px var(--font-sans)",
          color: "var(--text-strong)",
          letterSpacing: "-0.2px",
        }}
      >
        {title}
      </div>
      <div style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-muted)", marginTop: 6 }}>
        {text}
      </div>
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}
