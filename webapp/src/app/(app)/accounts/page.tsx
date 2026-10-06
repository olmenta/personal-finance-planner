"use client";

import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/shadcn/dropdown-menu";
import { Separator } from "@/components/shadcn/separator";
import { useAccounts } from "@/components/AccountPicker";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { IconChip, type ChipTone } from "@/components/ui/IconChip";
import { Input } from "@/components/ui/Input";
import { Panel } from "@/components/ui/Panel";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TopBar } from "@/components/shell/TopBar";
import {
  ApiError,
  convertToLoan,
  createAccount,
  currentMonth,
  updateAccount,
  type AccountOut,
  type AccountType,
  type AccountUpdate,
} from "@/lib/api";
import { euroCents, parseEuroToCents } from "@/lib/format";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { monthFromIndex, monthIndex, monthLabel } from "@/lib/schedules";

const TYPE_META: Record<AccountType, { icon: string; tone: ChipTone; label: string }> = {
  bank: { icon: "landmark", tone: "violet", label: "Bank account" },
  cash: { icon: "wallet", tone: "mint", label: "Cash" },
  credit: { icon: "credit-card", tone: "info", label: "Credit card" },
};

const TYPE_OPTIONS = [
  { value: "bank", label: "Bank" },
  { value: "cash", label: "Cash" },
  { value: "credit", label: "Card" },
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "account_exists") {
    return "You already have an account with that name.";
  }
  return "That didn't save — check the backend is running and try again.";
}

/* "" = not set; anything else must be a day of the month. */
function parseDay(input: string): number | null | undefined {
  if (!input.trim()) return null;
  const day = Number(input);
  return Number.isInteger(day) && day >= 1 && day <= 31 ? day : undefined;
}

const dialogStyle: React.CSSProperties = {
  borderRadius: "var(--r-2xl)",
  maxWidth: 440,
  border: "1px solid var(--border-hairline)",
  boxShadow: "var(--shadow-xl)",
};

const titleStyle: React.CSSProperties = {
  font: "700 19px var(--font-sans)",
  letterSpacing: "-0.4px",
  color: "var(--text-strong)",
};

function ErrorNote({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div
      role="alert"
      style={{
        font: "600 13px var(--font-sans)",
        color: "var(--expense)",
        background: "var(--expense-soft)",
        borderRadius: "var(--r-md)",
        padding: "9px 12px",
      }}
    >
      {children}
    </div>
  );
}

function useAccountWrite() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["transactions"] });
    // A card brings (or renames/archives) its payment category.
    queryClient.invalidateQueries({ queryKey: ["categories"] });
    invalidateMoneyQueries(queryClient);
  };
}

function AddAccountDialog({ open, onClose }: Readonly<{ open: boolean; onClose: () => void }>) {
  const [name, setName] = React.useState("");
  const [type, setType] = React.useState<AccountType>("bank");
  const [balance, setBalance] = React.useState("");
  const [paymentDay, setPaymentDay] = React.useState("");
  const refresh = useAccountWrite();

  const isCredit = type === "credit";
  const balanceCents = balance.trim() ? parseEuroToCents(balance) : 0;
  const day = parseDay(paymentDay);

  const mutation = useMutation({
    mutationFn: () =>
      createAccount({
        name: name.trim(),
        type,
        // A card's starting balance is what you owe: stored as negative.
        opening_balance_cents: balanceCents
          ? isCredit
            ? -balanceCents
            : balanceCents
          : undefined,
        payment_day: isCredit && day ? day : undefined,
      }),
    onSuccess: () => {
      refresh();
      setName("");
      setType("bank");
      setBalance("");
      setPaymentDay("");
      onClose();
    },
  });

  const canSubmit =
    !!name.trim() &&
    balanceCents !== null &&
    balanceCents >= 0 &&
    (!isCredit || day !== undefined) &&
    !mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="p-0 gap-0 overflow-hidden" style={dialogStyle}>
        <DialogHeader
          style={{ padding: "22px 24px 18px", borderBottom: "1px solid var(--border-hairline)" }}
        >
          <DialogTitle style={titleStyle}>Add account</DialogTitle>
          <div style={{ marginTop: 12 }}>
            <SegmentedControl
              options={TYPE_OPTIONS}
              value={type}
              onChange={(v) => setType(v as AccountType)}
            />
          </div>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) mutation.mutate();
          }}
        >
          <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <Input
              label="Name"
              placeholder={isCredit ? "Visa BBVA" : "Cuenta nómina"}
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Input
              label={isCredit ? "What you owe on it today" : "Current balance"}
              help={
                isCredit
                  ? "Optional. Existing card debt doesn't touch your budget — you pay it down by assigning money to the card."
                  : "Optional. It becomes money ready to assign."
              }
              prefix="€"
              inputMode="decimal"
              placeholder="0,00"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
              inputStyle={{ fontVariantNumeric: "tabular-nums" }}
            />
            {isCredit && (
              <Input
                label="Which day is the card charged?"
                help="Optional — skip it if you don't know. We'll suggest one from your statements."
                inputMode="numeric"
                placeholder="10"
                value={paymentDay}
                onChange={(e) => setPaymentDay(e.target.value)}
                error={day === undefined ? "Use a day between 1 and 31" : undefined}
              />
            )}
            {mutation.isError && <ErrorNote>{errorMessage(mutation.error)}</ErrorNote>}
          </div>
          <Separator style={{ background: "var(--border-hairline)" }} />
          <div style={{ padding: "16px 24px", display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <Button variant="ghost" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" iconLeft="plus" disabled={!canSubmit}>
              Add account
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditAccountDialog({
  account,
  onClose,
}: Readonly<{ account: AccountOut | null; onClose: () => void }>) {
  return (
    <Dialog open={account !== null} onOpenChange={(o) => !o && onClose()}>
      {account && <EditAccountForm key={account.id} account={account} onClose={onClose} />}
    </Dialog>
  );
}

function EditAccountForm({
  account,
  onClose,
}: Readonly<{ account: AccountOut; onClose: () => void }>) {
  const [name, setName] = React.useState(account.name);
  const [paymentDay, setPaymentDay] = React.useState(
    account.payment_day ? String(account.payment_day) : "",
  );
  const refresh = useAccountWrite();
  const isCredit = account.type === "credit";
  const day = parseDay(paymentDay);

  const mutation = useMutation({
    mutationFn: () => {
      const patch: AccountUpdate = {};
      if (name.trim() !== account.name) patch.name = name.trim();
      if (isCredit && day !== undefined && day !== account.payment_day) patch.payment_day = day;
      return updateAccount(account.id, patch);
    },
    onSuccess: () => {
      refresh();
      onClose();
    },
  });

  const canSubmit = !!name.trim() && (!isCredit || day !== undefined) && !mutation.isPending;

  return (
    <DialogContent className="p-0 gap-0 overflow-hidden" style={dialogStyle}>
      <DialogHeader
        style={{ padding: "22px 24px 18px", borderBottom: "1px solid var(--border-hairline)" }}
      >
        <DialogTitle style={titleStyle}>Edit account</DialogTitle>
      </DialogHeader>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) mutation.mutate();
        }}
      >
        <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
          <Input label="Name" autoFocus value={name} onChange={(e) => setName(e.target.value)} />
          {isCredit && (
            <Input
              label="Which day is the card charged?"
              help="Leave it empty if you don't know."
              inputMode="numeric"
              placeholder="10"
              value={paymentDay}
              onChange={(e) => setPaymentDay(e.target.value)}
              error={day === undefined ? "Use a day between 1 and 31" : undefined}
            />
          )}
          {mutation.isError && <ErrorNote>{errorMessage(mutation.error)}</ErrorNote>}
        </div>
        <Separator style={{ background: "var(--border-hairline)" }} />
        <div style={{ padding: "16px 24px", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" type="submit" disabled={!canSubmit}>
            Save changes
          </Button>
        </div>
      </form>
    </DialogContent>
  );
}

/* A loan that was set up as a card becomes an installment loan in
   "What you owe" (spec: accounts-api, debts design D6). */
function ConvertToLoanDialog({
  account,
  onClose,
}: Readonly<{ account: AccountOut | null; onClose: () => void }>) {
  return (
    <Dialog open={account !== null} onOpenChange={(o) => !o && onClose()}>
      {account && <ConvertToLoanForm key={account.id} account={account} onClose={onClose} />}
    </Dialog>
  );
}

function ConvertToLoanForm({
  account,
  onClose,
}: Readonly<{ account: AccountOut; onClose: () => void }>) {
  const refresh = useAccountWrite();
  const queryClient = useQueryClient();
  const nextDefault = monthFromIndex(monthIndex(currentMonth()) + 1);
  const [installment, setInstallment] = React.useState("");
  const [left, setLeft] = React.useState("");
  const [nextMonth, setNextMonth] = React.useState(nextDefault);
  const [day, setDay] = React.useState(account.payment_day ? String(account.payment_day) : "");
  const installmentCents = parseEuroToCents(installment);
  const count = Number(left);
  const mutation = useMutation({
    mutationFn: () =>
      convertToLoan(account.id, {
        installment_cents: installmentCents ?? 0,
        installments_left: count,
        next_month: nextMonth,
        day: parseDay(day) ?? null,
      }),
    onSuccess: () => {
      refresh();
      queryClient.invalidateQueries({ queryKey: ["debts"] });
      onClose();
    },
  });
  const canSubmit = !!installmentCents && installmentCents > 0 && count >= 1 && !mutation.isPending;
  const months = Array.from({ length: 13 }, (_, k) => monthFromIndex(monthIndex(currentMonth()) + k));

  return (
    <DialogContent className="p-0 gap-0 overflow-hidden" style={dialogStyle}>
      <DialogHeader style={{ padding: "22px 24px 18px", borderBottom: "1px solid var(--border-hairline)" }}>
        <DialogTitle style={titleStyle}>This is a loan, not a card</DialogTitle>
      </DialogHeader>
      <form
        aria-label="Convert to loan"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) mutation.mutate();
        }}
      >
        <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
          <p style={{ font: "500 14px/1.5 var(--font-sans)", color: "var(--text-muted)", margin: 0 }}>
            {account.name} moves to What you owe as a loan with installments. The account is archived and its
            history stays.
          </p>
          <Input label="Each installment" prefix="€" inputMode="decimal" placeholder="0,00"
            value={installment} onChange={(e) => setInstallment(e.target.value)} />
          <Input label="Installments left" inputMode="numeric" placeholder="34"
            value={left} onChange={(e) => setLeft(e.target.value.replace(/\D/g, ""))} />
          <label style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>Next one</span>
            <select
              aria-label="Next one"
              value={nextMonth}
              onChange={(e) => setNextMonth(e.target.value)}
              style={{ height: 44, borderRadius: 10, border: "1.5px solid var(--border-hairline)", padding: "0 10px", font: "500 14px var(--font-sans)", background: "var(--surface)", color: "var(--text-strong)" }}
            >
              {months.map((m) => (
                <option key={m} value={m}>{monthLabel(m)}</option>
              ))}
            </select>
          </label>
          <Input label="Day of the month (optional)" inputMode="numeric" placeholder="—"
            value={day} onChange={(e) => setDay(e.target.value.replace(/\D/g, "").slice(0, 2))} />
          {mutation.isError && <ErrorNote>That didn&apos;t work — check the numbers and try again.</ErrorNote>}
        </div>
        <Separator style={{ background: "var(--border-hairline)" }} />
        <div style={{ padding: "16px 24px", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" type="submit" disabled={!canSubmit}>Move to What you owe</Button>
        </div>
      </form>
    </DialogContent>
  );
}

function AccountRow({
  account,
  last,
  onEdit,
  onConvert,
}: Readonly<{
  account: AccountOut;
  last: boolean;
  onEdit: (a: AccountOut) => void;
  onConvert: (a: AccountOut) => void;
}>) {
  const refresh = useAccountWrite();
  const patch = useMutation({
    mutationFn: (body: AccountUpdate) => updateAccount(account.id, body),
    onSuccess: refresh,
  });
  const meta = TYPE_META[account.type];
  const isCredit = account.type === "credit";
  const owed = Math.max(0, -account.balance_cents);
  const uncovered = account.uncovered_debt_cents ?? 0;

  const sub = [meta.label, account.institution].filter(Boolean).join(" · ");
  let dayLine: string | null = null;
  if (isCredit && account.payment_day) dayLine = `Charged on day ${account.payment_day}`;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 13,
        padding: "14px 0",
        borderBottom: last ? "none" : "1px solid var(--border-hairline)",
        opacity: account.archived ? 0.6 : 1,
      }}
    >
      <IconChip icon={meta.icon} tone={meta.tone} size={42} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span
            style={{
              font: "600 15px var(--font-sans)",
              color: "var(--text-strong)",
              letterSpacing: "-0.1px",
            }}
          >
            {account.name}
          </span>
          {account.is_main && <Badge tone="neutral">Main</Badge>}
        </div>
        <div style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)", marginTop: 1 }}>
          {[sub, dayLine].filter(Boolean).join(" · ")}
        </div>
        {/* Suggest-never-apply: the inferred day waits for the user's tap. */}
        {isCredit && !account.payment_day && account.suggested_payment_day && !account.archived && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
            <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-body)" }}>
              Your payments land around day {account.suggested_payment_day}.
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={patch.isPending}
              onClick={() => patch.mutate({ payment_day: account.suggested_payment_day })}
            >
              Set day {account.suggested_payment_day}
            </Button>
          </div>
        )}
      </div>
      <div style={{ textAlign: "right", flex: "none" }}>
        {/* Card debt reads as an amount owed, in neutral color — never a red negative. */}
        <div
          style={{
            font: "700 15.5px var(--font-sans)",
            color: "var(--text-strong)",
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "-0.2px",
          }}
        >
          {isCredit
            ? owed > 0
              ? `You owe ${euroCents(owed)}`
              : euroCents(account.balance_cents)
            : euroCents(account.balance_cents)}
        </div>
        {isCredit && uncovered > 0 && (
          <div
            style={{
              font: "600 12px var(--font-sans)",
              color: "var(--warning)",
              marginTop: 2,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {euroCents(uncovered)} not covered
          </div>
        )}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <IconButton icon="more-horizontal" variant="ghost" size="sm" ariaLabel="Account actions" />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          style={{
            borderRadius: "var(--r-md)",
            border: "1px solid var(--border-hairline)",
            boxShadow: "var(--shadow-lg)",
          }}
        >
          <DropdownMenuItem onSelect={() => onEdit(account)}>Edit</DropdownMenuItem>
          {isCredit && !account.archived && (
            <DropdownMenuItem onSelect={() => onConvert(account)}>This is a loan, not a card</DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={() => patch.mutate({ archived: !account.archived })}>
            {account.archived ? "Restore" : "Archive"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

export default function AccountsPage() {
  const query = useAccounts();
  const [adding, setAdding] = React.useState(false);
  const [editing, setEditing] = React.useState<AccountOut | null>(null);
  const [converting, setConverting] = React.useState<AccountOut | null>(null);
  const archived = query.all.filter((a) => a.archived);

  // Cash and bank money you hold; card debt is reported per card.
  const held = query.active
    .filter((a) => a.type !== "credit")
    .reduce((sum, a) => sum + a.balance_cents, 0);

  let body: React.ReactNode;
  if (query.isPending) {
    body = <SkeletonPanel rows={3} rowHeight={56} />;
  } else if (query.isError) {
    body = <ErrorPanel message="We couldn't load your accounts." onRetry={() => query.refetch()} />;
  } else {
    body = (
      <>
        <Panel
          title="Your accounts"
          action={
            <Button variant="primary" size="sm" iconLeft="plus" onClick={() => setAdding(true)}>
              Add account
            </Button>
          }
        >
          {query.active.length === 0 ? (
            <p style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", margin: 0 }}>
              Add the accounts and cards you use so every euro has a home.
            </p>
          ) : (
            query.active.map((a, i) => (
              <AccountRow
                key={a.id}
                account={a}
                last={i === query.active.length - 1}
                onEdit={setEditing}
                onConvert={setConverting}
              />
            ))
          )}
        </Panel>
        {archived.length > 0 && (
          <Panel title="Archived">
            {archived.map((a, i) => (
              <AccountRow key={a.id} account={a} last={i === archived.length - 1} onEdit={setEditing} onConvert={setConverting} />
            ))}
          </Panel>
        )}
      </>
    );
  }

  return (
    <>
      <TopBar
        title="Accounts"
        sub={query.data ? `${euroCents(held)} in cash and bank accounts` : "Where your money sits"}
      />
      <div className="app-content" style={{ maxWidth: 720 }}>
        {body}
      </div>
      <AddAccountDialog open={adding} onClose={() => setAdding(false)} />
      <EditAccountDialog account={editing} onClose={() => setEditing(null)} />
      <ConvertToLoanDialog account={converting} onClose={() => setConverting(null)} />
    </>
  );
}
