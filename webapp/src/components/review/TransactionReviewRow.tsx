"use client";

import React from "react";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Input } from "@/components/ui/Input";
import { PayeeField } from "@/components/PayeeField";
import { CategoryCombobox, type CategoryComboboxProps } from "@/components/CategoryCombobox";
import type { PayeeOut, TwinMatch } from "@/lib/api";
import { euroCents } from "@/lib/format";

/** Picker value for "Transfer → <account>": the row's twin lands there. */
export const TRANSFER_PREFIX = "transfer:";

/** What a review row needs from a staged or confirmed transaction. */
export interface ReviewRowData {
  id: string;
  date: string;
  amount_cents: number;
  description: string | null;
  match?: TwinMatch | null;
}

export type MatchDecision = "accept" | "ignore";

const NO_GROUPS: NonNullable<CategoryComboboxProps["extraGroups"]> = [];

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

export interface TransactionReviewRowProps {
  row: ReviewRowData;
  last: boolean;
  selection: string;
  payee: string;
  note: string;
  payees: PayeeOut[];
  onSelect: (id: string, value: string) => void;
  onPayee: (id: string, value: string) => void;
  onNote: (id: string, value: string) => void;
  /** Badge in the category cell ("Suggested", a confidence level…). */
  badgeLabel?: string | null;
  badgeTone?: BadgeTone;
  /** Import only: "Transfers →" picker entries and twin-match suggestions. */
  transferGroups?: CategoryComboboxProps["extraGroups"];
  decision?: MatchDecision;
  matchAccountName?: string | null;
  onDecision?: (id: string, value: MatchDecision | null) => void;
}

/* One reviewable transaction row, shared by the import review and the AI
   categorization review: date, editable note, payee, amount, category picker.

   Memoized with a stable-props contract: every prop is a primitive, the row
   object from its query, a list memoized by the dialog, or a dispatcher
   created once with useCallback. Passing a new inline object or function
   here would make every row re-render on each keystroke again. */
export const TransactionReviewRow = React.memo(function TransactionReviewRow({
  row: t,
  last,
  selection,
  payee,
  note,
  payees,
  onSelect,
  onPayee,
  onNote,
  badgeLabel = null,
  badgeTone = "brand",
  transferGroups = NO_GROUPS,
  decision,
  matchAccountName = null,
  onDecision,
}: Readonly<TransactionReviewRowProps>) {
  const isIncome = t.amount_cents > 0;
  const isTransfer = selection.startsWith(TRANSFER_PREFIX);
  const adopted = decision === "accept";
  const columns = "58px minmax(0, 1fr) 190px 96px 220px";
  return (
    <div
      // Named by the original bank text, so a row stays findable while its
      // note is being edited.
      role="group"
      aria-label={t.description ?? "Transaction"}
      style={{
        opacity: adopted ? 0.55 : 1,
        display: "grid",
        gridTemplateColumns: columns,
        gap: 10,
        alignItems: "center",
        padding: "10px 12px",
        borderBottom: last ? "none" : "1px solid var(--border-hairline)",
      }}
    >
      <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
        {formatDate(t.date)}
      </span>
      {/* The note is the row's description: the bank text comes prefilled
          and any edit replaces it. */}
      <Input
        aria-label="Note"
        placeholder="Add a note"
        title={t.description ?? undefined}
        disabled={adopted}
        value={note}
        maxLength={500}
        onChange={(e) => onNote(t.id, e.target.value)}
      />
      {isTransfer || adopted ? (
        <span />
      ) : (
        <PayeeField
          label=""
          value={payee}
          payees={payees}
          onChange={(value) => onPayee(t.id, value)}
          onPick={(p) => onPayee(t.id, p.name)}
        />
      )}
      <span
        style={{
          textAlign: "right",
          font: "700 13.5px var(--font-sans)",
          fontVariantNumeric: "tabular-nums",
          // Transfers are neutral: money moving between pockets.
          color: isIncome && !isTransfer && !adopted ? "var(--income)" : "var(--text-strong)",
        }}
      >
        {isIncome ? "+" : "−"}
        {euroCents(Math.abs(t.amount_cents))}
      </span>
      {/* Inflows default to "Ready to assign" (income); picking a category
          turns them into refunds that restore that category. */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
        <CategoryCombobox
          size="sm"
          value={selection}
          disabled={adopted}
          noneLabel={isIncome ? "Ready to assign" : "Uncategorized"}
          extraGroups={transferGroups}
          placeholder="Pick a category"
          onChange={(value) => onSelect(t.id, value)}
        />
        {badgeLabel && !isTransfer && <Badge tone={badgeTone}>{badgeLabel}</Badge>}
      </div>
      {t.match && onDecision && decision !== "ignore" && (
        <div
          style={{
            gridColumn: "2 / -1",
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 8,
            font: "500 12.5px var(--font-sans)",
            color: "var(--text-muted)",
          }}
        >
          <Icon name="arrow-left-right" size={14} />
          <span>
            {adopted ? "Linked to the" : "Looks like the"} transfer {isIncome ? "from" : "to"}{" "}
            <strong style={{ color: "var(--text-strong)" }}>{matchAccountName}</strong> on{" "}
            {formatDate(t.match.date)}
            {adopted ? " — this row won't be added twice." : "."}
          </span>
          {adopted ? (
            <Button variant="ghost" size="sm" type="button" onClick={() => onDecision(t.id, null)}>
              Undo
            </Button>
          ) : (
            <>
              <Button
                variant="secondary"
                size="sm"
                type="button"
                onClick={() => onDecision(t.id, "accept")}
              >
                Link them
              </Button>
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={() => onDecision(t.id, "ignore")}
              >
                Keep separate
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
});
