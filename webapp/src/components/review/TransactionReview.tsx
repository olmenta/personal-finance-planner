"use client";

import React from "react";
import { TransactionReviewRow } from "./TransactionReviewRow";
import type { ReviewItem, useTransactionReview } from "./useTransactionReview";

export interface TransactionReviewProps {
  items: ReviewItem[];
  review: ReturnType<typeof useTransactionReview>;
  /** Rendered instead of the list when there is nothing to review. */
  empty?: React.ReactNode;
  maxHeight?: number | string;
}

/* The list both reviews render (spec: transaction-review): the import's
   staged rows and the confirmed uncategorized ones look and behave alike. */
export function TransactionReview({
  items,
  review,
  empty,
  maxHeight = 380,
}: Readonly<TransactionReviewProps>) {
  return (
    <div
      style={{
        maxHeight,
        overflowY: "auto",
        border: "1px solid var(--border-hairline)",
        borderRadius: "var(--r-lg)",
      }}
    >
      {items.length === 0
        ? empty
        : items.map((item, i) => (
            <TransactionReviewRow key={item.row.id} {...review.rowProps(item, i === items.length - 1)} />
          ))}
    </div>
  );
}
