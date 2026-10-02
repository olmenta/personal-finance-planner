"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/shadcn/dialog";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import { Separator } from "@/components/shadcn/separator";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { PayeeField } from "@/components/PayeeField";
import {
  ApiError,
  confirmImport,
  discardImport,
  fetchCategories,
  fetchPayees,
  fetchPendingImport,
  uploadImport,
  type ImportBank,
  type ImportBatchView,
} from "@/lib/api";
import { euroCents } from "@/lib/format";
import { useCoverPrompt } from "@/components/budget/CoverPrompt";

const UNCATEGORIZED = "none";

interface SourceOption {
  id: ImportBank;
  label: string;
  description: string;
  accept: string;
}

const SOURCES: SourceOption[] = [
  {
    id: "bbva",
    label: "BBVA - es",
    description: "The .xlsx export from BBVA online banking",
    accept: ".xlsx",
  },
  {
    id: "sabadell",
    label: "Sabadell - es",
    description: "The .xls export from Banco Sabadell",
    accept: ".xls",
  },
  {
    id: "custom",
    label: "Custom CSV",
    description:
      "Any other bank — fill our CSV template with date, amount and description (category and balance are optional)",
    accept: ".csv",
  },
];

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

function uploadErrorCode(error: unknown, isError: boolean): string | null {
  if (error instanceof ApiError) {
    // 409 import_pending is navigation to the pending review, not an error (design D5).
    return error.code === "import_pending" ? null : error.code;
  }
  return isError ? "unknown_error" : null;
}

export interface ImportBankTransactionsDialogProps {
  children: React.ReactNode;
}

export function ImportBankTransactionsDialog({
  children,
}: ImportBankTransactionsDialogProps) {
  const [open, setOpen] = React.useState(false);
  const [bank, setBank] = React.useState<ImportBank | null>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [batch, setBatch] = React.useState<ImportBatchView | null>(null);
  const [selections, setSelections] = React.useState<Record<string, string>>({});
  // Row payee edits; absent key = keep the AI-staged payee untouched.
  const [payeeEdits, setPayeeEdits] = React.useState<Record<string, string>>({});
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const queryClient = useQueryClient();
  const { data: groups } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
    enabled: open,
  });
  const { data: payees } = useQuery({
    queryKey: ["payees"],
    queryFn: fetchPayees,
    enabled: open,
  });
  const pendingQuery = useQuery({
    queryKey: ["imports", "pending"],
    queryFn: fetchPendingImport,
    enabled: open,
  });

  // Resume mode (design D3): with a pending batch and no fresh upload, the
  // dialog reviews the pending one — whatever opened it lands on the review
  // step instead of the source picker.
  const activeBatch = batch ?? pendingQuery.data ?? null;

  const upload = useMutation({
    mutationFn: ({ file, bank }: { file: File; bank: ImportBank }) =>
      uploadImport(file, bank),
    onSuccess: (view) => {
      setBatch(view);
      setSelections({});
      setPayeeEdits({});
      // Staging may have created AI-proposed payees.
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      queryClient.setQueryData(["imports", "pending"], view);
      queryClient.invalidateQueries({ queryKey: ["imports", "pending"] });
    },
    onError: (error) => {
      // 409 import_pending is navigation, not an error wall (design D5):
      // refetch the pending batch and activeBatch swaps to its review.
      if (error instanceof ApiError && error.code === "import_pending") {
        queryClient.invalidateQueries({ queryKey: ["imports", "pending"] });
      }
    },
  });

  // A row's category: explicit pick, else the staged AI suggestion.
  const selectionFor = (t: { id: string; category_id: string | null }) =>
    selections[t.id] ?? t.category_id ?? UNCATEGORIZED;

  const promptCover = useCoverPrompt();
  const confirm = useMutation({
    mutationFn: () => {
      const overrides: Record<string, string | null> = {};
      const payeeOverrides: Record<string, string> = {};
      for (const t of activeBatch?.transactions ?? []) {
        const picked = selectionFor(t);
        const pickedId = picked === UNCATEGORIZED ? null : picked;
        if (pickedId !== t.category_id) overrides[t.id] = pickedId;
        const edited = (payeeEdits[t.id] ?? t.payee_name ?? "").trim();
        if (edited !== (t.payee_name ?? "").trim()) payeeOverrides[t.id] = edited;
      }
      return confirmImport(activeBatch!.id, overrides, payeeOverrides);
    },
    onSuccess: (confirmed) => {
      // Imports span months, unlike single adds — invalidate each one.
      const months = new Set(
        (activeBatch?.transactions ?? []).map((t) => t.date.slice(0, 7)),
      );
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      // Imports leave payees null today, but every transaction mutation
      // refreshes the payee memory (spec: webapp-server-state).
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      for (const m of months) {
        queryClient.invalidateQueries({ queryKey: ["budget", m] });
        queryClient.invalidateQueries({ queryKey: ["summary", m] });
      }
      // Synchronous null first — the resume effect must not re-adopt the
      // just-confirmed batch from stale cache.
      queryClient.setQueryData(["imports", "pending"], null);
      queryClient.invalidateQueries({ queryKey: ["imports", "pending"] });
      reset();
      setOpen(false);
      // Overspent now? Offer the cover for the first month that needs it.
      const touched = new Map<string, string[]>();
      for (const t of confirmed.transactions) {
        if (!t.category_id) continue;
        const m = t.date.slice(0, 7);
        touched.set(m, [...(touched.get(m) ?? []), t.category_id]);
      }
      void (async () => {
        for (const [m, ids] of [...touched].sort(([a], [b]) => b.localeCompare(a))) {
          if (await promptCover(m, ids)) return;
        }
      })();
    },
  });

  const discard = useMutation({
    mutationFn: () => discardImport(activeBatch!.id),
    onSuccess: () => {
      queryClient.setQueryData(["imports", "pending"], null);
      queryClient.invalidateQueries({ queryKey: ["imports", "pending"] });
      // Discard may have deleted batch-only payees from autocomplete.
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      setBatch(null);
      setSelections({});
      setPayeeEdits({});
      setFile(null);
      upload.reset();
    },
  });

  function reset() {
    setBank(null);
    setFile(null);
    setBatch(null);
    setSelections({});
    setPayeeEdits({});
    upload.reset();
    confirm.reset();
    discard.reset();
  }

  function handleOpenChange(next: boolean) {
    // Closing mid-review keeps the batch staged — the transactions screen
    // shows a resume banner and reopening lands back on this review.
    if (!next) reset();
    setOpen(next);
  }

  const selectedSource = SOURCES.find((s) => s.id === bank);
  const uploadError = uploadErrorCode(upload.error, upload.isError);

  const reviewing = activeBatch !== null && activeBatch.status === "staged";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>

      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{
          borderRadius: "var(--r-2xl)",
          // Review step takes 3/4 of the screen; floor keeps phones usable
          // (the w-full base class stretches up to this cap).
          maxWidth: reviewing ? "max(75vw, 360px)" : 480,
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <DialogHeader
          style={{
            padding: "22px 24px 18px",
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
            {reviewing ? "Review your import" : "Import bank transactions"}
          </DialogTitle>
          {!reviewing && (
            <p
              style={{
                font: "500 13.5px var(--font-sans)",
                color: "var(--text-muted)",
                margin: "4px 0 0",
              }}
            >
              Pick your bank, upload its export, and review every row before it
              touches your budget.
            </p>
          )}
        </DialogHeader>

        {!reviewing ? (
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
            <div role="radiogroup" aria-label="Available banks" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {SOURCES.map((source) => {
                const selected = bank === source.id;
                return (
                  <button
                    key={source.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => {
                      setBank(source.id);
                      setFile(null);
                      upload.reset();
                    }}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 12,
                      textAlign: "left",
                      padding: "12px 14px",
                      borderRadius: "var(--r-lg)",
                      border: selected
                        ? "1.5px solid var(--brand)"
                        : "1.5px solid var(--border-hairline)",
                      background: selected ? "var(--violet-50)" : "var(--surface)",
                      cursor: "pointer",
                    }}
                  >
                    <span
                      style={{
                        marginTop: 2,
                        width: 16,
                        height: 16,
                        flex: "none",
                        borderRadius: "50%",
                        border: selected
                          ? "5px solid var(--brand)"
                          : "1.5px solid var(--gray-400)",
                        background: "var(--surface)",
                      }}
                    />
                    <span>
                      <span
                        style={{
                          display: "block",
                          font: "600 14.5px var(--font-sans)",
                          color: "var(--text-strong)",
                          letterSpacing: "-0.1px",
                        }}
                      >
                        {source.label}
                      </span>
                      <span
                        style={{
                          display: "block",
                          font: "500 12.5px var(--font-sans)",
                          color: "var(--text-muted)",
                          marginTop: 2,
                        }}
                      >
                        {source.description}
                      </span>
                      {source.id === "custom" && selected && (
                        <a
                          href="/import-template.csv"
                          download
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 5,
                            marginTop: 8,
                            font: "600 13px var(--font-sans)",
                            color: "var(--violet-700)",
                          }}
                        >
                          <Icon name="download" size={14} strokeWidth={2.5} />
                          Download the template
                        </a>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept={selectedSource?.accept ?? ".xlsx,.xls,.csv"}
              style={{ display: "none" }}
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                upload.reset();
              }}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Button
                variant="ghost"
                size="sm"
                type="button"
                iconLeft="upload"
                disabled={!bank}
                onClick={() => fileInputRef.current?.click()}
              >
                {file ? "Choose another file" : "Choose the file"}
              </Button>
              {file && (
                <span
                  className="ol-mono"
                  style={{ font: "500 12.5px var(--font-mono)", color: "var(--text-muted)" }}
                >
                  {file.name}
                </span>
              )}
            </div>

            {uploadError && (
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
                {uploadError === "file_format_unrecognized"
                  ? `That file doesn't match the ${selectedSource?.label ?? "selected"} format — pick another file or a different bank.`
                  : uploadError === "file_too_large"
                    ? "That file is too big — export a shorter date range and try again."
                    : "We couldn't reach the server — try the upload again."}
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: "16px 24px 20px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingBottom: 12,
              }}
            >
              <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>
                {activeBatch.row_count} {activeBatch.row_count === 1 ? "transaction" : "transactions"} ready to
                import
              </span>
              {activeBatch.skipped_duplicates > 0 && (
                <Badge tone="neutral" icon="check">
                  {activeBatch.skipped_duplicates}{" "}
                  {activeBatch.skipped_duplicates === 1 ? "row" : "rows"} already
                  imported — skipped
                </Badge>
              )}
            </div>

            <div
              style={{
                maxHeight: 380,
                overflowY: "auto",
                border: "1px solid var(--border-hairline)",
                borderRadius: "var(--r-lg)",
              }}
            >
              {activeBatch.row_count === 0 ? (
                <div
                  style={{
                    padding: "28px 16px",
                    textAlign: "center",
                    font: "500 13.5px var(--font-sans)",
                    color: "var(--text-muted)",
                  }}
                >
                  <div
                    style={{
                      font: "700 14.5px var(--font-sans)",
                      color: "var(--text-strong)",
                      marginBottom: 6,
                    }}
                  >
                    These transactions are already in
                  </div>
                  Every row in this file matches a transaction you imported
                  before — check your transactions list to see them. Discard
                  this review to import a different file.
                </div>
              ) : (
                activeBatch.transactions.map((t, i) => {
                  const isIncome = t.amount_cents > 0;
                  const suggested =
                    t.category_id !== null && selectionFor(t) === t.category_id;
                  return (
                    <div
                      key={t.id}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "58px minmax(0, 1fr) 190px 96px 180px",
                        gap: 10,
                        alignItems: "center",
                        padding: "10px 12px",
                        borderBottom:
                          i < activeBatch.transactions.length - 1
                            ? "1px solid var(--border-hairline)"
                            : "none",
                      }}
                    >
                      <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
                        {formatDate(t.date)}
                      </span>
                      <span
                        style={{
                          font: "600 13.5px var(--font-sans)",
                          color: "var(--text-strong)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={t.description ?? undefined}
                      >
                        {t.description}
                      </span>
                      <PayeeField
                        label=""
                        value={payeeEdits[t.id] ?? t.payee_name ?? ""}
                        payees={payees ?? []}
                        onChange={(value) =>
                          setPayeeEdits((prev) => ({ ...prev, [t.id]: value }))
                        }
                        onPick={(p) =>
                          setPayeeEdits((prev) => ({ ...prev, [t.id]: p.name }))
                        }
                      />
                      <span
                        style={{
                          textAlign: "right",
                          font: "700 13.5px var(--font-sans)",
                          fontVariantNumeric: "tabular-nums",
                          color: isIncome ? "var(--income)" : "var(--text-strong)",
                        }}
                      >
                        {isIncome ? "+" : "−"}
                        {euroCents(Math.abs(t.amount_cents))}
                      </span>
                      {/* Positive rows default to "Ready to assign" (income);
                          picking a category turns them into refunds that
                          restore that category (spec: statement-import). */}
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Select
                          value={selectionFor(t)}
                          onValueChange={(value) =>
                            setSelections((prev) => ({ ...prev, [t.id]: value }))
                          }
                        >
                          <SelectTrigger
                            className="h-9 rounded-[8px] border text-xs font-medium w-full"
                            style={{
                              borderColor: "var(--border-hairline)",
                              background: "var(--surface)",
                              fontFamily: "var(--font-sans)",
                              color:
                                selectionFor(t) === UNCATEGORIZED
                                  ? "var(--text-subtle)"
                                  : "var(--text-strong)",
                            }}
                          >
                            <SelectValue placeholder="Pick a category" />
                          </SelectTrigger>
                          <SelectContent
                            style={{
                              borderRadius: "var(--r-md)",
                              border: "1px solid var(--border-hairline)",
                              boxShadow: "var(--shadow-lg)",
                            }}
                          >
                            <SelectItem value={UNCATEGORIZED}>
                              {isIncome ? "Ready to assign" : "Uncategorized"}
                            </SelectItem>
                            {(groups ?? []).map((g) => (
                              <SelectGroup key={g.id}>
                                <SelectLabel>{g.name}</SelectLabel>
                                {g.categories.filter((c) => !c.archived).map((c) => (
                                  <SelectItem key={c.id} value={c.id}>
                                    {c.name}
                                  </SelectItem>
                                ))}
                              </SelectGroup>
                            ))}
                          </SelectContent>
                        </Select>
                        {suggested && <Badge tone="brand">Suggested</Badge>}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {(confirm.isError || discard.isError) && (
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
                That didn&apos;t go through — check the backend is running and try again.
              </div>
            )}
          </div>
        )}

        <Separator style={{ background: "var(--border-hairline)" }} />

        <div
          style={{
            padding: "16px 24px",
            display: "flex",
            justifyContent: "flex-end",
            gap: 10,
          }}
        >
          {!reviewing ? (
            <>
              <Button variant="ghost" size="sm" type="button" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                type="button"
                iconLeft="upload"
                disabled={!bank || !file || upload.isPending}
                onClick={() => bank && file && upload.mutate({ file, bank })}
              >
                {upload.isPending ? "Reading the file…" : "Upload and review"}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                type="button"
                disabled={discard.isPending || confirm.isPending}
                onClick={() => discard.mutate()}
              >
                Discard
              </Button>
              <Button
                variant="primary"
                size="sm"
                type="button"
                iconLeft="check"
                disabled={confirm.isPending || activeBatch.row_count === 0}
                onClick={() => confirm.mutate()}
              >
                {confirm.isPending ? "Importing…" : "Confirm import"}
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
