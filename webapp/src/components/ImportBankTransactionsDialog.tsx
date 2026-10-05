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
import { Separator } from "@/components/shadcn/separator";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { NO_CATEGORY } from "@/components/CategoryCombobox";
import { TransactionReview } from "@/components/review/TransactionReview";
import { useTransactionReview, type ReviewItem } from "@/components/review/useTransactionReview";
import { AccountSelect, useAccounts } from "@/components/AccountPicker";
import {
  ApiError,
  confirmImport,
  discardImport,
  fetchPendingImport,
  uploadImport,
  type ImportBank,
  type ImportBatchView,
} from "@/lib/api";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { useCoverPrompt } from "@/components/budget/CoverPrompt";


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
  // "" = the main account.
  const [uploadAccountId, setUploadAccountId] = React.useState("");
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const queryClient = useQueryClient();
  const pendingQuery = useQuery({
    queryKey: ["imports", "pending"],
    queryFn: fetchPendingImport,
    enabled: open,
  });
  const { active: accounts, main } = useAccounts(open);

  // Resume mode (design D3): with a pending batch and no fresh upload, the
  // dialog reviews the pending one — whatever opened it lands on the review
  // step instead of the source picker.
  const activeBatch = batch ?? pendingQuery.data ?? null;

  // The shared review (spec: transaction-review): the staged AI category is
  // each row's default, badged "Suggested" while kept.
  const items = React.useMemo<ReviewItem[]>(
    () =>
      (activeBatch?.transactions ?? []).map((t) => ({
        row: t,
        defaultSelection: t.category_id ?? NO_CATEGORY,
        defaultPayee: t.payee_name ?? "",
        badgeLabel: t.category_id !== null ? "Suggested" : null,
      })),
    [activeBatch],
  );
  const review = useTransactionReview(items, open);

  const upload = useMutation({
    mutationFn: ({ file, bank }: { file: File; bank: ImportBank }) =>
      uploadImport(file, bank, uploadAccountId || undefined),
    onSuccess: (view) => {
      setBatch(view);
      review.reset();
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

  const promptCover = useCoverPrompt();
  const confirm = useMutation({
    mutationFn: () => confirmImport(activeBatch!.id, review.buildDecisions()),
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
      invalidateMoneyQueries(queryClient);
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
      review.reset();
      setFile(null);
      upload.reset();
    },
  });

  function reset() {
    setBank(null);
    setFile(null);
    setBatch(null);
    review.reset();
    setUploadAccountId("");
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

            {accounts.length > 1 && (
              <AccountSelect
                label="Import into"
                value={uploadAccountId || main?.id || ""}
                onChange={setUploadAccountId}
                accounts={accounts}
              />
            )}

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

            <TransactionReview
              items={items}
              review={review}
              empty={
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
              }
            />

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
