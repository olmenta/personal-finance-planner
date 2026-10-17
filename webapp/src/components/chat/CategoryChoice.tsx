"use client";

import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/shadcn/select";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import {
  ActionStaleError,
  commitCoachAction,
  resolveCategoryChoice,
  undoCoachAction,
  type CoachAction,
  type GroupChoice,
} from "@/lib/api";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { actionError } from "./Actions";

/* A new category, chosen by the user (spec: coach-conversation, creating a
   category). Similar categories come first as "Use X"; creating takes a
   group from the dropdown (the suggested one preselected) or a new group.
   Nothing is created until the user picks, and the step it was for (an
   expense, an amount) appears next as its own preview. */

const NEW_GROUP = "__new_group__";

const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const card: React.CSSProperties = {
  border: "1px solid var(--border-hairline)",
  borderRadius: "var(--r-lg)",
  padding: "14px 16px",
  display: "flex",
  flexDirection: "column",
  gap: 12,
  background: "var(--surface)",
};
const muted: React.CSSProperties = { font: "500 13px var(--font-sans)", color: "var(--text-muted)" };

export function CategoryChoice({ action: shown }: Readonly<{ action: CoachAction }>) {
  const queryClient = useQueryClient();
  const [action, setAction] = React.useState(shown);
  const [prev, setPrev] = React.useState(shown);
  if (prev.id !== shown.id || prev.status !== shown.status || prev.can_undo !== shown.can_undo) {
    setPrev(shown);
    setAction(shown);
  }
  const p = action.preview;
  const groups = p.groups ?? [];
  const [group, setGroup] = React.useState<string>(p.suggested_group_id ?? groups[0]?.id ?? NEW_GROUP);
  const [newGroup, setNewGroup] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const keyRef = React.useRef<string | null>(null);

  const refresh = () => {
    invalidateMoneyQueries(queryClient);
    queryClient.invalidateQueries({ queryKey: ["categories"] });
  };
  const onError = (e: unknown) => {
    if (e instanceof ActionStaleError) {
      keyRef.current = null;
      setAction(e.action);
      setError("Your categories changed since: check the options again.");
      return;
    }
    setError(actionError(e));
  };

  const use = useMutation({
    mutationFn: (categoryId: string) => resolveCategoryChoice(action.id, categoryId),
    onSuccess: (r) => {
      setError(null);
      setAction(r.action);
      refresh();
    },
    onError,
  });
  const create = useMutation({
    mutationFn: () => {
      keyRef.current ??= newKey();
      const choice: GroupChoice = group === NEW_GROUP ? { new_group_name: newGroup.trim() } : { group_id: group };
      return commitCoachAction(action.id, action.revision, keyRef.current, choice);
    },
    onSuccess: (r) => {
      setError(null);
      setAction(r.action);
      refresh();
    },
    onError,
  });
  const undo = useMutation({
    mutationFn: () => undoCoachAction(action.id),
    onSuccess: (a) => {
      setAction(a);
      refresh();
    },
    onError,
  });

  const groupName = (id: string | undefined) => groups.find((g) => g.id === id)?.name;
  const result = action.result as { category_id?: string; group_id?: string; created_group?: boolean } | null;

  if (action.status !== "proposed") {
    const usedName = p.similar?.find((s) => s.id === result?.category_id)?.name;
    const text =
      action.status === "resolved"
        ? `Using ${usedName ?? "an existing category"}`
        : action.status === "undone"
          ? `Not created: ${p.name}`
          : action.status === "applied"
            ? `Created ${p.name}${result?.created_group ? " in a new group" : groupName(result?.group_id) ? ` in ${groupName(result?.group_id)}` : ""}`
            : action.status === "stale"
              ? "Needs updating"
              : "Cancelled";
    return (
      <div data-testid="category-choice" data-status={action.status} style={{ ...card, background: "var(--surface-sunk)", border: "none", flexDirection: "row", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, font: "600 14.5px var(--font-sans)", color: "var(--text-strong)" }}>
          <Icon name={action.status === "undone" ? "undo" : "check-circle"} size={18} color={action.status === "undone" ? "var(--text-muted)" : "var(--accent)"} />
          {text}
        </span>
        {action.status === "applied" && action.can_undo && (
          <Button size="sm" variant="secondary" iconLeft="undo" disabled={undo.isPending} onClick={() => undo.mutate()}>
            Undo
          </Button>
        )}
        {error && <div role="alert" style={{ font: "600 13px var(--font-sans)", color: "var(--expense)", width: "100%" }}>{error}</div>}
      </div>
    );
  }

  const busy = use.isPending || create.isPending;
  const canCreate = group !== NEW_GROUP || newGroup.trim().length > 0;
  return (
    <div data-testid="category-choice" data-status={action.status} style={card}>
      <div style={{ font: "700 15px var(--font-sans)", color: "var(--text-strong)" }}>
        No category for &ldquo;{p.name}&rdquo; yet
      </div>
      {p.follow_up_title && <div style={muted}>Then: {p.follow_up_title}</div>}
      {(p.similar ?? []).length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={muted}>Use one you already have:</span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {(p.similar ?? []).map((s) => (
              <Button key={s.id} size="sm" variant="secondary" disabled={busy} onClick={() => use.mutate(s.id)}>
                Use {s.name} · {s.group_name}
              </Button>
            ))}
          </div>
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, borderTop: "1px solid var(--border-hairline)", paddingTop: 12 }}>
        <span style={muted}>Or create &ldquo;{p.name}&rdquo; in:</span>
        <Select value={group} onValueChange={setGroup}>
          <SelectTrigger aria-label="Group for the new category" className="h-[38px] rounded-xl text-sm" style={{ fontFamily: "var(--font-sans)", maxWidth: 320 }}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {groups.map((g) => (
              <SelectItem key={g.id} value={g.id}>
                {g.name}
                {g.id === p.suggested_group_id ? " (suggested)" : ""}
              </SelectItem>
            ))}
            <SelectItem value={NEW_GROUP}>New group…</SelectItem>
          </SelectContent>
        </Select>
        {group === NEW_GROUP && (
          <input
            aria-label="New group name"
            placeholder="Group name"
            value={newGroup}
            maxLength={120}
            onChange={(e) => setNewGroup(e.target.value)}
            style={{ maxWidth: 320, border: "1px solid var(--border-hairline)", borderRadius: "var(--r-md)", padding: "9px 12px", font: "500 14px var(--font-sans)" }}
          />
        )}
        <div>
          <Button size="sm" iconLeft="plus" disabled={busy || !canCreate} onClick={() => create.mutate()}>
            Create category
          </Button>
        </div>
      </div>
      {error && <div role="alert" style={{ font: "600 13px var(--font-sans)", color: "var(--expense)" }}>{error}</div>}
    </div>
  );
}
