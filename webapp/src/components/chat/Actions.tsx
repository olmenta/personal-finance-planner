"use client";

import Link from "next/link";
import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import {
  ActionStaleError,
  ApiError,
  cancelCoachAction,
  commitCoachAction,
  createCoachAction,
  undoCoachAction,
  type CoachAction,
  type CoachActionIn,
} from "@/lib/api";
import { euroCents, money, parseEuroToCents } from "@/lib/format";
import { monthLabel } from "@/lib/schedules";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { useConversationActions } from "./ConversationContext";

/* Action preview and result (spec: coach-conversation, action lifecycle).
   Every number is the server's preview; nothing changes until Confirm, and
   Undo is offered only while the server says it's still valid. */

const ERRORS: Record<string, string> = {
  insufficient_to_be_assigned: "There isn't enough unassigned money for this anymore.",
  insufficient_available: "That category doesn't have enough money left for this.",
  assignment_from_payments: "This category is computed from its payments, so it can't be set by hand.",
  category_required: "An expense needs a category.",
  already_applied: "This change was already made.",
  action_closed: "This change is no longer open.",
  undo_not_possible: "Something it changed was edited since, so it can't be undone. Ask me for a new review.",
};

export const actionError = (e: unknown) =>
  (e instanceof ApiError && ERRORS[e.code]) || "That didn't work. Try again.";

const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const sameAction = (a: CoachAction, b: CoachAction) =>
  a.id === b.id && a.status === b.status && a.can_undo === b.can_undo;

/** Local action state that follows the server's copy when a refetch changes
    it, and keeps local updates (a commit's result) in between. */
function useActionState(shown: CoachAction) {
  const [action, setAction] = React.useState(shown);
  const [prev, setPrev] = React.useState(shown);
  if (!sameAction(prev, shown)) {
    setPrev(shown);
    setAction(shown);
  }
  return [action, setAction] as const;
}

const row: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  font: "500 14px var(--font-sans)",
  color: "var(--text-body)",
  fontVariantNumeric: "tabular-nums",
};

function Change({ label, before, after }: Readonly<{ label: string; before: number; after: number }>) {
  return (
    <div style={row}>
      <span>{label}</span>
      <span style={{ whiteSpace: "nowrap" }}>
        {euroCents(before)} <Icon name="arrow-right" size={13} style={{ verticalAlign: -2 }} />{" "}
        <b style={{ color: "var(--text-strong)" }}>{euroCents(after)}</b>
      </span>
    </div>
  );
}

function PaymentBody({ action }: Readonly<{ action: CoachAction }>) {
  const p = action.preview;
  const pay = p.payment!;
  const a = p.amounts!;
  const c = p.categories[0];
  return (
    <div data-testid="payment-preview" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ font: "600 14px/1.45 var(--font-sans)", color: "var(--text-strong)" }}>
        {pay.sentence_before && (
          <span style={{ color: "var(--text-muted)", textDecoration: pay.sentence_after ? "none" : "line-through" }}>
            {pay.sentence_before}
            {pay.sentence_after && " → "}
          </span>
        )}
        {pay.sentence_after}
        {pay.estimated && <span style={{ ...row, display: "inline", color: "var(--text-muted)", fontWeight: 500 }}> · Estimated</span>}
      </div>
      <Change label="Monthly amount" before={a.normal_before_cents} after={a.normal_after_cents} />
      {(a.catch_up_before_cents !== a.normal_before_cents || a.catch_up_after_cents !== a.normal_after_cents) && (
        <Change label="To be on time" before={a.catch_up_before_cents} after={a.catch_up_after_cents} />
      )}
      {c && <Change label={`${c.name} this month`} before={c.assigned_before_cents} after={c.assigned_after_cents} />}
      {p.to_be_assigned_before_cents !== p.to_be_assigned_after_cents && (
        <Change label="To be assigned" before={p.to_be_assigned_before_cents} after={p.to_be_assigned_after_cents} />
      )}
      {pay.next_due_month && (
        <div style={{ ...row, color: "var(--text-muted)" }}>
          <span>Next payment</span>
          <span>{monthLabel(pay.next_due_month)}</span>
        </div>
      )}
      <Link href="/budgets" style={{ font: "600 13px var(--font-sans)", color: "var(--brand)", alignSelf: "flex-start" }}>
        See its payments in Budget
      </Link>
    </div>
  );
}

const STATUS_WORDS: Record<string, string> = {
  received: "received",
  pending: "expected",
  late: "not arrived yet",
  missed: "didn't arrive",
};

/** The year's coverage in words, from the plan summary's gap. */
function coverage(known: boolean, gap: number | null): string {
  if (!known || gap === null) return "unknown";
  return gap >= 0 ? "covered" : `short ${euroCents(-gap)} a year`;
}

function IncomeBody({ action }: Readonly<{ action: CoachAction }>) {
  const p = action.preview;
  const plan = p.plan!;
  const link = p.link;
  return (
    <div data-testid="income-preview" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {link ? (
        <>
          <div style={row}>
            <span>{link.occurrence_after?.name ?? "Expected income"}</span>
            <span>
              {STATUS_WORDS[link.occurrence_before?.status ?? ""] ?? "expected"}{" "}
              <Icon name="arrow-right" size={13} style={{ verticalAlign: -2 }} />{" "}
              <b style={{ color: "var(--text-strong)" }}>{STATUS_WORDS[link.occurrence_after?.status ?? ""] ?? "expected"}</b>
            </span>
          </div>
          {!link.unplanned_after && (
            <div style={{ ...row, color: "var(--text-muted)" }}>
              <span>{euroCents(link.amount_cents)} is no longer unplanned</span>
            </div>
          )}
        </>
      ) : (
        <>
          <div style={{ font: "600 14px/1.45 var(--font-sans)", color: "var(--text-strong)" }}>
            {p.income?.sentence_before && (
              <span style={{ color: "var(--text-muted)", textDecoration: p.income.sentence_after ? "none" : "line-through" }}>
                {p.income.sentence_before}
                {p.income.sentence_after && " → "}
              </span>
            )}
            {p.income?.sentence_after}
            {p.income?.estimated && <span style={{ color: "var(--text-muted)", fontWeight: 500 }}> · Estimated</span>}
          </div>
          <Change label="Expected this month" before={plan.month_expected_before_cents} after={plan.month_expected_after_cents} />
          <Change label="Expected over 12 months" before={plan.year_expected_before_cents} after={plan.year_expected_after_cents} />
          <div style={row} data-testid="income-coverage">
            <span>Your year</span>
            <span>
              {coverage(plan.income_known_before, plan.gap_before_cents)}{" "}
              <Icon name="arrow-right" size={13} style={{ verticalAlign: -2 }} />{" "}
              <b style={{ color: "var(--text-strong)" }}>{coverage(plan.income_known_after, plan.gap_after_cents)}</b>
            </span>
          </div>
        </>
      )}
      <div style={{ ...row, color: "var(--text-muted)" }}>
        <span>To be assigned changes only when the money arrives</span>
      </div>
    </div>
  );
}

function PreviewBody({ action }: Readonly<{ action: CoachAction }>) {
  const p = action.preview;
  const t = p.transaction;
  if (p.payment) return <PaymentBody action={action} />;
  if (p.plan || p.link) return <IncomeBody action={action} />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {t && (
        <div style={{ ...row, flexWrap: "wrap" }}>
          <span>
            {t.direction === "income" ? "Income" : "Expense"}
            {t.payee ? ` · ${t.payee}` : ""}
            {t.category_name ? ` · ${t.category_name}` : ""}
            {` · ${new Date(t.date).toLocaleDateString("es-ES")}`}
            {t.account_name ? ` · ${t.account_name}` : ""}
          </span>
          <b style={{ color: t.direction === "income" ? "var(--income)" : "var(--text-strong)" }}>
            {t.direction === "income" ? "+" : "−"}
            {euroCents(t.amount_cents)}
          </b>
        </div>
      )}
      {p.categories.map((c) =>
        action.kind === "assignments" ? (
          <Change key={c.category_id} label={`${c.name}: assigned`} before={c.assigned_before_cents} after={c.assigned_after_cents} />
        ) : (
          <Change key={c.category_id} label={`${c.name}: available`} before={c.available_before_cents} after={c.available_after_cents} />
        ),
      )}
      {p.to_be_assigned_before_cents !== p.to_be_assigned_after_cents && (
        <Change label="To be assigned" before={p.to_be_assigned_before_cents} after={p.to_be_assigned_after_cents} />
      )}
      {p.accounts_unchanged && (
        <div style={{ ...row, color: "var(--text-muted)" }}>
          <span>Money in accounts</span>
          <span>unchanged</span>
        </div>
      )}
    </div>
  );
}

const card: React.CSSProperties = {
  border: "1px solid var(--border-hairline)",
  borderRadius: "var(--r-lg)",
  padding: "14px 16px",
  display: "flex",
  flexDirection: "column",
  gap: 10,
  background: "var(--surface)",
};

const STATUS_TEXT: Record<CoachAction["status"], string> = {
  proposed: "Review before confirming",
  applied: "Done",
  stale: "Needs updating",
  cancelled: "Cancelled",
  undone: "Undone",
  resolved: "Done",
};

/** Amount fields for Edit: one per move, or the one amount. */
function editableAmounts(action: CoachAction): number[] {
  const c = action.command;
  if (c.moves) return c.moves.map((m) => m.amount_cents);
  if (c.items) return c.items.map((i) => i.amount_cents);
  return [c.amount_cents ?? 0];
}

/** The label of each amount field in Edit. */
function amountLabel(action: CoachAction, i: number): string {
  return action.command.moves?.[i]?.to_name ?? action.command.items?.[i]?.category_name ?? "Amount";
}

function edited(action: CoachAction, amounts: number[]): CoachActionIn {
  const c = action.command;
  if (action.kind === "moves") {
    return {
      kind: "moves",
      replaces: action.id,
      moves: (c.moves ?? []).map((m, i) => ({
        from_category_id: m.from_category_id,
        to_category_id: m.to_category_id,
        amount_cents: amounts[i],
      })),
    };
  }
  if (action.kind === "assignments") {
    return {
      kind: "assignments",
      replaces: action.id,
      items: (c.items ?? []).map((item, i) => ({ category_id: item.category_id, amount_cents: amounts[i] })),
    };
  }
  if (action.kind === "assignment") {
    return { kind: "assignment", replaces: action.id, category_id: c.category_id, amount_cents: amounts[0] };
  }
  return {
    kind: "transaction",
    replaces: action.id,
    amount_cents: amounts[0],
    direction: c.direction,
    category_id: c.category_id,
    payee: c.payee,
    date: c.date,
    account_id: c.account_id,
    note: c.note,
  };
}

export function ActionPreview({ action: shown }: Readonly<{ action: CoachAction }>) {
  const queryClient = useQueryClient();
  const { markStale, isStaleReplacement } = useConversationActions();
  const [action, setAction] = useActionState(shown);
  const [error, setError] = React.useState<string | null>(null);
  const [editing, setEditing] = React.useState<string[] | null>(null);
  const keyRef = React.useRef<string | null>(null);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["coach-conversation"] });
    queryClient.invalidateQueries({ queryKey: ["coach-actions"] });
  };

  const confirm = useMutation({
    mutationFn: () => {
      keyRef.current ??= newKey(); // one key per confirm intent: a retry can't apply twice
      return commitCoachAction(action.id, action.revision, keyRef.current);
    },
    onSuccess: (result) => {
      setError(null);
      setAction(result.action);
      invalidateMoneyQueries(queryClient);
    },
    onError: (e) => {
      if (e instanceof ActionStaleError) {
        keyRef.current = null;
        markStale(e.action.id);
        setAction(e.action);
        refresh();
        return;
      }
      setError(actionError(e));
    },
  });
  const cancel = useMutation({
    mutationFn: () => cancelCoachAction(action.id),
    onSuccess: (a) => {
      setAction(a);
      refresh();
    },
    onError: (e) => setError(actionError(e)),
  });
  const save = useMutation({
    mutationFn: (amounts: number[]) => createCoachAction(edited(action, amounts)),
    onSuccess: (a) => {
      setEditing(null);
      setError(null);
      setAction(a);
      refresh();
    },
    onError: (e) => setError(actionError(e)),
  });

  if (action.status === "applied" || action.status === "undone") {
    return <ActionResult action={action} />;
  }
  const open = action.status === "proposed";
  const stale = isStaleReplacement(action.id);
  return (
    <div data-testid="action-preview" data-status={action.status} style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", flexWrap: "wrap" }}>
        <span style={{ font: "700 15px var(--font-sans)", color: "var(--text-strong)" }}>{action.title}</span>
        <span style={{ font: "600 12.5px var(--font-sans)", color: open ? "var(--text-muted)" : "var(--text-subtle)" }}>
          {STATUS_TEXT[action.status]}
        </span>
      </div>
      {stale && open && (
        <div role="status" data-testid="needs-updating" style={{ font: "600 13px var(--font-sans)", color: "#8A5300", background: "var(--warning-soft)", borderRadius: "var(--r-md)", padding: "8px 10px" }}>
          Needs updating: the numbers changed since the first preview. These are the current ones.
        </div>
      )}
      <PreviewBody action={action} />
      {editing && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {editing.map((value, i) => (
            <label key={i} style={{ ...row, alignItems: "center" }}>
              <span>{amountLabel(action, i)}</span>
              <input
                aria-label={`Amount ${i + 1}`}
                inputMode="decimal"
                value={value}
                onChange={(e) => setEditing(editing.map((v, j) => (j === i ? e.target.value : v)))}
                style={{ width: 120, textAlign: "right", border: "1px solid var(--border-hairline)", borderRadius: "var(--r-sm)", padding: "6px 8px", font: "600 14px var(--font-sans)", fontVariantNumeric: "tabular-nums" }}
              />
            </label>
          ))}
        </div>
      )}
      {error && (
        <div role="alert" style={{ font: "600 13px var(--font-sans)", color: "var(--expense)" }}>{error}</div>
      )}
      {open && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {editing ? (
            <>
              <Button
                size="sm"
                disabled={save.isPending}
                onClick={() => {
                  const cents = editing.map((v) => parseEuroToCents(v));
                  const zeroOk = action.kind === "assignments"; // clearing a category is a valid budget
                  if (cents.some((c) => c === null || c < 0 || (c === 0 && !zeroOk))) {
                    setError("Enter amounts greater than zero.");
                    return;
                  }
                  save.mutate(cents as number[]);
                }}
              >
                Update the preview
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                Keep it as it was
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" iconLeft="check" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
                Confirm
              </Button>
              {!action.kind.startsWith("payment") && !action.kind.startsWith("income") && (
                <Button size="sm" variant="secondary" iconLeft="pencil" onClick={() => setEditing(editableAmounts(action).map((c) => money(c / 100)))}>
                  Edit
                </Button>
              )}
              <Button size="sm" variant="ghost" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
                Cancel
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function ActionResult({ action: shown }: Readonly<{ action: CoachAction }>) {
  const queryClient = useQueryClient();
  const [action, setAction] = useActionState(shown);
  const [error, setError] = React.useState<string | null>(null);
  const undo = useMutation({
    mutationFn: () => undoCoachAction(action.id),
    onSuccess: (a) => {
      setError(null);
      setAction(a);
      invalidateMoneyQueries(queryClient);
    },
    onError: (e) => setError(actionError(e)),
  });
  const undone = action.status === "undone";
  return (
    <div data-testid="action-result" data-status={action.status} style={{ ...card, background: "var(--surface-sunk)", border: "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "space-between", flexWrap: "wrap" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, font: "600 14.5px var(--font-sans)", color: "var(--text-strong)" }}>
          <Icon name={undone ? "undo" : "check-circle"} size={18} color={undone ? "var(--text-muted)" : "var(--accent)"} />
          {undone ? `Undone: ${action.title}` : `Done: ${action.title}`}
        </span>
        {!undone && action.can_undo && (
          <Button size="sm" variant="secondary" iconLeft="undo" disabled={undo.isPending} onClick={() => undo.mutate()}>
            Undo
          </Button>
        )}
      </div>
      {!undone && !action.can_undo && (
        <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
          Can&apos;t be undone anymore: something it changed was edited since.
        </span>
      )}
      {error && (
        <div role="alert" style={{ font: "600 13px var(--font-sans)", color: "var(--expense)" }}>{error}</div>
      )}
    </div>
  );
}
