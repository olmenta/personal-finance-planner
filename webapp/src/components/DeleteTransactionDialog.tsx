"use client";

import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import { Separator } from "@/components/shadcn/separator";
import { Button } from "@/components/ui/Button";
import { deleteTransaction, deleteTransfer, type TransactionOut } from "@/lib/api";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { euroCents } from "@/lib/format";

export interface DeleteTransactionDialogProps {
  transaction: TransactionOut | null; // null = closed
  onClose: () => void;
}

export function DeleteTransactionDialog({
  transaction,
  onClose,
}: DeleteTransactionDialogProps) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    // A transfer row deletes through the transfer contract — both twins go.
    mutationFn: (txn: TransactionOut) =>
      txn.transfer_pair_id ? deleteTransfer(txn.transfer_pair_id) : deleteTransaction(txn.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      invalidateMoneyQueries(queryClient);
      onClose();
    },
  });

  const label =
    transaction &&
    (transaction.payee_name ?? transaction.description ?? "this transaction");

  return (
    <Dialog open={transaction !== null} onOpenChange={(o) => !o && onClose()}>
      {transaction && (
        <DialogContent
          className="p-0 gap-0 overflow-hidden"
          style={{
            borderRadius: "var(--r-2xl)",
            maxWidth: 420,
            border: "1px solid var(--border-hairline)",
            boxShadow: "var(--shadow-xl)",
          }}
        >
          <DialogHeader style={{ padding: "22px 24px 14px" }}>
            <DialogTitle
              style={{
                font: "700 19px var(--font-sans)",
                letterSpacing: "-0.4px",
                color: "var(--text-strong)",
              }}
            >
              Delete transaction?
            </DialogTitle>
          </DialogHeader>

          <div style={{ padding: "0 24px 20px" }}>
            <p
              style={{
                font: "500 14.5px var(--font-sans)",
                color: "var(--text-body)",
                margin: 0,
              }}
            >
              {label} ·{" "}
              <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>
                {euroCents(Math.abs(transaction.amount_cents))}
              </span>{" "}
              {transaction.transfer_pair_id
                ? "will be removed from both accounts."
                : "will be removed permanently and your totals will update."}
            </p>

            {mutation.isError && (
              <div
                role="alert"
                style={{
                  marginTop: 14,
                  font: "600 13px var(--font-sans)",
                  color: "var(--expense)",
                  background: "var(--expense-soft)",
                  borderRadius: "var(--r-md)",
                  padding: "9px 12px",
                }}
              >
                That didn&apos;t work — check the backend is running and try again.
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
            <Button
              variant="primary"
              size="sm"
              type="button"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(transaction)}
              style={{ background: "var(--expense)" }}
            >
              Delete transaction
            </Button>
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
