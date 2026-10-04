"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import { Separator } from "@/components/shadcn/separator";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon, OLMENTA_ICON_NAMES } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";
import { IconChip } from "@/components/ui/IconChip";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { ScheduleEditor } from "@/components/plan/ScheduleEditor";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { useSelectedMonth } from "@/lib/selectedMonth";
import {
  ApiError,
  createCategory,
  createCategoryGroup,
  deleteCategoryGroup,
  fetchBudgetMonth,
  fetchCategories,
  toneForCategory,
  updateCategory,
  updateCategoryGroup,
  type CategoryGroupOut,
  type CategoryOut,
} from "@/lib/api";

/* 409 codes → actionable copy (design D4: errors are messages, not dead ends). */
const ERROR_COPY: Record<string, string> = {
  category_exists: "A category with that name already exists in this group.",
  group_exists: "A group with that name already exists.",
  group_not_empty: "The group still has categories — move or archive them first.",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && ERROR_COPY[error.code]) {
    return ERROR_COPY[error.code];
  }
  return "That didn't save — check the backend is running and try again.";
}

function useInvalidateCategories() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["categories"] });
    // Names and icons render in the budget bars too.
    invalidateMoneyQueries(queryClient);
  };
}

const dialogContentStyle: React.CSSProperties = {
  borderRadius: "var(--r-2xl)",
  maxWidth: 440,
  border: "1px solid var(--border-hairline)",
  boxShadow: "var(--shadow-xl)",
};

const dialogTitleStyle: React.CSSProperties = {
  font: "700 19px var(--font-sans)",
  letterSpacing: "-0.4px",
  color: "var(--text-strong)",
};

function DialogShell({
  title,
  children,
  footer,
}: Readonly<{
  title: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}>) {
  return (
    <DialogContent className="p-0 gap-0 overflow-hidden" style={dialogContentStyle}>
      <DialogHeader
        style={{ padding: "22px 24px 14px", borderBottom: "1px solid var(--border-hairline)" }}
      >
        <DialogTitle style={dialogTitleStyle}>{title}</DialogTitle>
      </DialogHeader>
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
        {children}
      </div>
      <Separator style={{ background: "var(--border-hairline)" }} />
      <div style={{ padding: "16px 24px", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        {footer}
      </div>
    </DialogContent>
  );
}

function ErrorNote({ message }: Readonly<{ message: string }>) {
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
      {message}
    </div>
  );
}

function IconPicker({
  value,
  onChange,
}: Readonly<{ value: string; onChange: (name: string) => void }>) {
  return (
    <div>
      <div
        style={{
          font: "600 13.5px var(--font-sans)",
          color: "var(--text-body)",
          letterSpacing: "-0.1px",
          marginBottom: 7,
        }}
      >
        Icon
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(8, 1fr)",
          gap: 6,
          maxHeight: 168,
          overflowY: "auto",
          border: "1px solid var(--border-hairline)",
          borderRadius: "var(--r-md)",
          padding: 8,
        }}
      >
        {OLMENTA_ICON_NAMES.map((name) => {
          const selected = name === value;
          return (
            <button
              key={name}
              type="button"
              aria-label={name}
              aria-pressed={selected}
              onClick={() => onChange(name)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: 34,
                borderRadius: "var(--r-sm)",
                border: selected
                  ? "1.5px solid var(--brand)"
                  : "1px solid var(--border-hairline)",
                background: selected ? "var(--violet-50)" : "var(--surface)",
                cursor: "pointer",
              }}
            >
              <Icon
                name={name}
                size={17}
                color={selected ? "var(--brand)" : "var(--text-muted)"}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ---- Category create/edit dialog ------------------------------------------ */

interface CategoryDialogState {
  category: CategoryOut | null; // null = create
  groupId: string;
}

function CategoryDialog({
  state,
  groups,
  onClose,
}: Readonly<{
  state: CategoryDialogState | null;
  groups: CategoryGroupOut[];
  onClose: () => void;
}>) {
  return (
    <Dialog open={state !== null} onOpenChange={(o) => !o && onClose()}>
      {state && (
        <CategoryForm
          key={state.category?.id ?? "new"}
          state={state}
          groups={groups}
          onClose={onClose}
        />
      )}
    </Dialog>
  );
}

function CategoryForm({
  state,
  groups,
  onClose,
}: Readonly<{
  state: CategoryDialogState;
  groups: CategoryGroupOut[];
  onClose: () => void;
}>) {
  const editing = state.category;
  const [name, setName] = React.useState(editing?.name ?? "");
  const [icon, setIcon] = React.useState(editing?.icon ?? "circle");
  const [groupId, setGroupId] = React.useState(state.groupId);
  const [savings, setSavings] = React.useState(editing?.savings ?? false);
  const hasPayments = editing?.kind === "scheduled";
  const invalidate = useInvalidateCategories();

  const mutation = useMutation({
    mutationFn: () =>
      editing
        ? updateCategory(editing.id, { name: name.trim(), icon, group_id: groupId, savings })
        : createCategory({ name: name.trim(), icon, group_id: groupId, savings }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const canSubmit = name.trim().length > 0 && !!groupId && !mutation.isPending;

  return (
    <DialogShell
      title={editing ? "Edit category" : "Add category"}
      footer={
        <>
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate()}
          >
            {editing ? "Save changes" : "Add category"}
          </Button>
        </>
      }
    >
      <Input
        label="Name"
        placeholder="e.g. Mascotas"
        autoFocus
        value={name}
        maxLength={120}
        onChange={(e) => setName(e.target.value)}
      />
      <IconPicker value={icon} onChange={setIcon} />
      <label style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        <span
          style={{
            font: "600 13.5px var(--font-sans)",
            color: "var(--text-body)",
            letterSpacing: "-0.1px",
          }}
        >
          Group
        </span>
        <Select value={groupId} onValueChange={setGroupId}>
          <SelectTrigger
            className="h-12 rounded-[10px] border-[1.5px] text-sm font-medium"
            style={{
              borderColor: "var(--border-hairline)",
              color: "var(--text-strong)",
              background: "var(--surface)",
              fontFamily: "var(--font-sans)",
            }}
          >
            <SelectValue placeholder="Select group" />
          </SelectTrigger>
          <SelectContent
            style={{
              borderRadius: "var(--r-md)",
              border: "1px solid var(--border-hairline)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            {/* System groups ("Tarjetas de crédito") only hold card payment categories. */}
            {groups.filter((g) => !g.system).map((g) => (
              <SelectItem key={g.id} value={g.id}>
                {g.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </label>
      <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>
          Savings
          <span style={{ display: "block", font: "500 12px var(--font-sans)", color: "var(--text-muted)" }}>
            {hasPayments
              ? "This category has payments, so it's planned from them."
              : "Money kept here shows as saved for the future, never as left to spend."}
          </span>
        </span>
        <Switch checked={savings} onChange={setSavings} disabled={hasPayments} />
      </label>
      {mutation.isError && <ErrorNote message={errorMessage(mutation.error)} />}
    </DialogShell>
  );
}

/* ---- Group create/rename dialog -------------------------------------------- */

interface GroupDialogState {
  group: CategoryGroupOut | null; // null = create
}

function GroupDialog({
  state,
  onClose,
}: Readonly<{ state: GroupDialogState | null; onClose: () => void }>) {
  return (
    <Dialog open={state !== null} onOpenChange={(o) => !o && onClose()}>
      {state && <GroupForm key={state.group?.id ?? "new"} state={state} onClose={onClose} />}
    </Dialog>
  );
}

function GroupForm({
  state,
  onClose,
}: Readonly<{ state: GroupDialogState; onClose: () => void }>) {
  const editing = state.group;
  const [name, setName] = React.useState(editing?.name ?? "");
  const invalidate = useInvalidateCategories();

  const mutation = useMutation({
    mutationFn: () =>
      editing
        ? updateCategoryGroup(editing.id, { name: name.trim() })
        : createCategoryGroup({ name: name.trim() }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const canSubmit = name.trim().length > 0 && !mutation.isPending;

  return (
    <DialogShell
      title={editing ? "Rename group" : "Add group"}
      footer={
        <>
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate()}
          >
            {editing ? "Save changes" : "Add group"}
          </Button>
        </>
      }
    >
      <Input
        label="Name"
        placeholder="e.g. Coche"
        autoFocus
        value={name}
        maxLength={120}
        onChange={(e) => setName(e.target.value)}
      />
      {mutation.isError && <ErrorNote message={errorMessage(mutation.error)} />}
    </DialogShell>
  );
}

/* ---- Delete empty group confirmation ---------------------------------------- */

function DeleteGroupDialog({
  group,
  onClose,
}: Readonly<{ group: CategoryGroupOut | null; onClose: () => void }>) {
  const invalidate = useInvalidateCategories();
  const mutation = useMutation({
    mutationFn: (id: string) => deleteCategoryGroup(id),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  return (
    <Dialog open={group !== null} onOpenChange={(o) => !o && onClose()}>
      {group && (
        <DialogShell
          title="Delete group?"
          footer={
            <>
              <Button variant="ghost" size="sm" type="button" onClick={onClose}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                type="button"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate(group.id)}
                style={{ background: "var(--expense)" }}
              >
                Delete group
              </Button>
            </>
          }
        >
          <p
            style={{
              font: "500 14.5px var(--font-sans)",
              color: "var(--text-body)",
              margin: 0,
            }}
          >
            &ldquo;{group.name}&rdquo; will be removed. Groups can only be deleted
            when they have no categories.
          </p>
          {mutation.isError && <ErrorNote message={errorMessage(mutation.error)} />}
        </DialogShell>
      )}
    </Dialog>
  );
}

/* ---- The Settings section ---------------------------------------------------- */

export function CategorySettings() {
  const { data: groups } = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });
  const invalidate = useInvalidateCategories();

  const [categoryDialog, setCategoryDialog] = React.useState<CategoryDialogState | null>(null);
  const [groupDialog, setGroupDialog] = React.useState<GroupDialogState | null>(null);
  const [deletingGroup, setDeletingGroup] = React.useState<CategoryGroupOut | null>(null);
  const [scheduling, setScheduling] = React.useState<CategoryOut | null>(null);
  const [month] = useSelectedMonth();
  // What the category already holds this month, when the budget is cached.
  const budget = useQuery({ queryKey: ["budget", month], queryFn: () => fetchBudgetMonth(month) });
  const savedFor = (id: string) =>
    budget.data?.groups.flatMap((g) => g.categories).find((c) => c.id === id)?.rollover_cents ?? 0;

  const archiveMutation = useMutation({
    mutationFn: ({ id, archived }: { id: string; archived: boolean }) =>
      updateCategory(id, { archived }),
    onSuccess: invalidate,
  });

  const firstGroupId = groups?.[0]?.id ?? "";

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          margin: "4px 2px 6px",
        }}
      >
        <div className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>
          Categories
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            variant="ghost"
            size="sm"
            iconLeft="plus"
            onClick={() => setGroupDialog({ group: null })}
          >
            Add group
          </Button>
          <Button
            variant="secondary"
            size="sm"
            iconLeft="plus"
            disabled={!firstGroupId}
            onClick={() => setCategoryDialog({ category: null, groupId: firstGroupId })}
          >
            Add category
          </Button>
        </div>
      </div>

      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border-hairline)",
          borderRadius: "var(--r-xl)",
          padding: "4px 16px 12px",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        {(groups ?? []).map((group) => (
          <div key={group.id}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 0 4px",
              }}
            >
              <span className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>
                {group.name}
              </span>
              {!group.system && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <IconButton
                    icon="more-horizontal"
                    variant="ghost"
                    size="sm"
                    ariaLabel={`Actions for group ${group.name}`}
                  />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => setGroupDialog({ group })}>
                    Rename
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    disabled={group.categories.length > 0}
                    onSelect={() => setDeletingGroup(group)}
                    style={{ color: "var(--expense)" }}
                  >
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              )}
            </div>

            {group.categories.length === 0 && (
              <div
                style={{
                  font: "500 13px var(--font-sans)",
                  color: "var(--text-muted)",
                  padding: "6px 0 10px",
                }}
              >
                No categories yet — add one to start budgeting here.
              </div>
            )}

            {group.categories.map((category, i) => (
              <div
                key={category.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 13,
                  padding: "9px 0",
                  borderBottom:
                    i < group.categories.length - 1
                      ? "1px solid var(--border-hairline)"
                      : "none",
                  opacity: category.archived ? 0.65 : 1,
                }}
              >
                <IconChip
                  icon={category.icon}
                  tone={toneForCategory(category.icon)}
                  size={36}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      font: "600 14.5px var(--font-sans)",
                      color: "var(--text-strong)",
                      letterSpacing: "-0.1px",
                    }}
                  >
                    {category.name}
                  </span>
                </div>
                {category.archived && <Badge tone="neutral">Archived</Badge>}
                {/* A card's payment category follows its account (rename,
                    archive) — managed from the Accounts screen. */}
                {category.payment_account_id ? (
                  <Badge tone="neutral" icon="credit-card">
                    Card payment
                  </Badge>
                ) : (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <IconButton
                      icon="more-horizontal"
                      variant="ghost"
                      size="sm"
                      ariaLabel={`Actions for ${category.name}`}
                    />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onSelect={() => setCategoryDialog({ category, groupId: group.id })}
                    >
                      Edit
                    </DropdownMenuItem>
                    {!category.archived && (
                      <DropdownMenuItem onSelect={() => setScheduling(category)}>
                        Payments
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem
                      onSelect={() =>
                        archiveMutation.mutate({
                          id: category.id,
                          archived: !category.archived,
                        })
                      }
                    >
                      {category.archived ? "Unarchive" : "Archive"}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      <CategoryDialog
        state={categoryDialog}
        groups={groups ?? []}
        onClose={() => setCategoryDialog(null)}
      />
      <GroupDialog state={groupDialog} onClose={() => setGroupDialog(null)} />
      <DeleteGroupDialog group={deletingGroup} onClose={() => setDeletingGroup(null)} />
      {scheduling && (
        <ScheduleEditor
          open
          onOpenChange={(open) => !open && setScheduling(null)}
          categoryId={scheduling.id}
          categoryName={scheduling.name}
          month={month}
          savedCents={savedFor(scheduling.id)}
        />
      )}
    </div>
  );
}
