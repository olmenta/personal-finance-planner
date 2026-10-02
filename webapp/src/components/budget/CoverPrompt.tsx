"use client";

import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";
import { fetchBudgetMonth, type BudgetMonthView } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { useMoveMoney } from "@/lib/useBudgetMonth";
import { MoveMoneySheet } from "./MoveMoneySheet";

/* Post-save cover prompt (budget-rules, design D8): after a write lands, if a
   category it touched is now overspent, offer the server's cover suggestion.
   Never blocks the save — the dialog has already closed when this shows. */

type PromptCover = (month: string, categoryIds: string[]) => Promise<boolean>;

const CoverPromptContext = React.createContext<PromptCover>(async () => false);

export function useCoverPrompt(): PromptCover {
  return React.useContext(CoverPromptContext);
}

export function CoverPromptProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = React.useState<{ month: string; categoryId: string } | null>(null);

  const promptCover = React.useCallback<PromptCover>(
    async (month, categoryIds) => {
      try {
        const view = await queryClient.fetchQuery({
          queryKey: ["budget", month],
          queryFn: () => fetchBudgetMonth(month),
          staleTime: 0,
        });
        const hit = view.groups
          .flatMap((g) => g.categories)
          .filter((c) => categoryIds.includes(c.id) && c.overspent_cents > 0)
          .sort((a, b) => b.overspent_cents - a.overspent_cents)[0];
        if (!hit) return false;
        setPrompt({ month, categoryId: hit.id });
        return true;
      } catch {
        return false; // best-effort: the budget screen still shows the overspending
      }
    },
    [queryClient],
  );

  return (
    <CoverPromptContext.Provider value={promptCover}>
      {children}
      {prompt && (
        <CoverPromptCard
          key={`${prompt.month}:${prompt.categoryId}`}
          month={prompt.month}
          categoryId={prompt.categoryId}
          onDone={() => setPrompt(null)}
        />
      )}
    </CoverPromptContext.Provider>
  );
}

function CoverPromptCard({
  month,
  categoryId,
  onDone,
}: Readonly<{ month: string; categoryId: string; onDone: () => void }>) {
  const { data: view } = useQuery<BudgetMonthView>({
    queryKey: ["budget", month],
    queryFn: () => fetchBudgetMonth(month),
  });
  const { move } = useMoveMoney(month);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  const categories = view?.groups.flatMap((g) => g.categories) ?? [];
  const category = categories.find((c) => c.id === categoryId);
  const resolved = !!category && category.overspent_cents <= 0 && !sheetOpen;

  // Covered meanwhile (here or on the budget screen): nothing left to ask.
  React.useEffect(() => {
    if (resolved) onDone();
  }, [resolved, onDone]);

  if (!view || !category || resolved) return null;

  const suggestion = category.cover_suggestion;
  const sourceName =
    suggestion?.source_category_id === null
      ? "unassigned"
      : categories.find((c) => c.id === suggestion?.source_category_id)?.name;

  return (
    <>
      <div
        role="status"
        className="cover-prompt"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border-hairline)",
          borderRadius: "var(--r-xl)",
          boxShadow: "var(--shadow-lg)",
          padding: "14px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <span
            style={{
              width: 32,
              height: 32,
              flex: "none",
              borderRadius: "var(--r-sm)",
              background: "var(--expense-soft)",
              color: "var(--expense)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name="arrow-left-right" size={16} />
          </span>
          <div style={{ flex: 1, font: "500 14px/1.4 var(--font-sans)", color: "var(--text-body)" }}>
            <b style={{ color: "var(--text-strong)" }}>{category.name}</b> is{" "}
            <b style={{ color: "var(--expense)", fontVariantNumeric: "tabular-nums" }}>
              {euroCents(category.overspent_cents)}
            </b>{" "}
            over. That money already left your account — cover it from another category now.
          </div>
          <IconButton icon="x" variant="ghost" size="sm" ariaLabel="Dismiss" onClick={onDone} />
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
          <Button variant="secondary" size="sm" onClick={() => setSheetOpen(true)}>
            Choose another
          </Button>
          {suggestion && sourceName && (
            <Button
              variant="accent"
              size="sm"
              onClick={() => {
                move({
                  from_category_id: suggestion.source_category_id,
                  to_category_id: category.id,
                  amount_cents: suggestion.amount_cents,
                });
                onDone();
              }}
            >
              Cover {euroCents(suggestion.amount_cents)} from {sourceName}
            </Button>
          )}
        </div>
      </div>
      <MoveMoneySheet
        open={sheetOpen}
        onOpenChange={(open) => {
          setSheetOpen(open);
          if (!open) onDone();
        }}
        view={view}
        initialTo={category.id}
        onMove={move}
      />
    </>
  );
}
