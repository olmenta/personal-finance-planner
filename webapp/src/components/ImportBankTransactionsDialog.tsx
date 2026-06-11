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
import {
  ApiError,
  confirmImport,
  discardImport,
  fetchCategories,
  uploadImport,
  type ImportBank,
  type ImportBatchView,
} from "@/lib/api";
import { euroCents } from "@/lib/format";

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
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const queryClient = useQueryClient();
  const { data: groups } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
    enabled: open,
  });

  const upload = useMutation({
    mutationFn: ({ file, bank }: { file: File; bank: ImportBank }) =>
      uploadImport(file, bank),
    onSuccess: (view) => {
      setBatch(view);
      const initial: Record<string, string> = {};
      for (const t of view.transactions) {
        initial[t.id] = t.category_id ?? UNCATEGORIZED;
      }
      setSelections(initial);
    },
  });

  const confirm = useMutation({
    mutationFn: () => {
      const overrides: Record<string, string | null> = {};
      for (const t of batch?.transactions ?? []) {
        const picked = selections[t.id] ?? UNCATEGORIZED;
        const pickedId = picked === UNCATEGORIZED ? null : picked;
        if (pickedId !== t.category_id) overrides[t.id] = pickedId;
      }
      return confirmImport(batch!.id, overrides);
    },
    onSuccess: (view) => {
      // Imports span months, unlike single adds — invalidate each one.
      const months = new Set(
        (batch?.transactions ?? []).map((t) => t.date.slice(0, 7)),
      );
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      // Imports leave payees null today, but every transaction mutation
      // refreshes the payee memory (spec: webapp-server-state).
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      for (const m of months) {
        queryClient.invalidateQueries({ queryKey: ["budget", m] });
        queryClient.invalidateQueries({ queryKey: ["summary", m] });
      }
      setBatch(view);
      reset();
      setOpen(false);
    },
  });

  const discard = useMutation({
    mutationFn: () => discardImport(batch!.id),
    onSuccess: () => {
      setBatch(null);
      setSelections({});
      setFile(null);
      upload.reset();
    },
  });

  function reset() {
    setBank(null);
    setFile(null);
    setBatch(null);
    setSelections({});
    upload.reset();
    confirm.reset();
    discard.reset();
  }

  function handleOpenChange(next: boolean) {
    if (!next && batch && batch.status === "staged" && !confirm.isPending) {
      // Closing mid-review abandons the batch — don't leave staged rows behind.
      discardImport(batch.id).catch(() => {});
    }
    if (!next) reset();
    setOpen(next);
  }

  const selectedSource = SOURCES.find((s) => s.id === bank);
  const uploadError =
    upload.error instanceof ApiError ? upload.error.code : upload.isError ? "unknown_error" : null;

  const reviewing = batch !== null && batch.status === "staged";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>

      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{
          borderRadius: "var(--r-2xl)",
          maxWidth: reviewing ? 640 : 480,
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
                {batch.row_count} {batch.row_count === 1 ? "transaction" : "transactions"} ready to
                import
              </span>
              {batch.skipped_duplicates > 0 && (
                <Badge tone="neutral" icon="check">
                  {batch.skipped_duplicates} duplicates skipped
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
              {batch.row_count === 0 ? (
                <div
                  style={{
                    padding: "28px 16px",
                    textAlign: "center",
                    font: "500 13.5px var(--font-sans)",
                    color: "var(--text-muted)",
                  }}
                >
                  Every row in this file is already in Olmenta — nothing new to import.
                </div>
              ) : (
                batch.transactions.map((t, i) => {
                  const isIncome = t.amount_cents > 0;
                  const suggested =
                    t.category_id !== null && selections[t.id] === t.category_id;
                  return (
                    <div
                      key={t.id}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "58px 1fr 96px 180px",
                        gap: 10,
                        alignItems: "center",
                        padding: "10px 12px",
                        borderBottom:
                          i < batch.transactions.length - 1
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
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Select
                          value={selections[t.id] ?? UNCATEGORIZED}
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
                                selections[t.id] === UNCATEGORIZED
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
                            <SelectItem value={UNCATEGORIZED}>Uncategorized</SelectItem>
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
                disabled={confirm.isPending || batch.row_count === 0}
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
