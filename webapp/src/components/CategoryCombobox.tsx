"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/shadcn/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/shadcn/popover";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import {
  ApiError,
  createCategory,
  fetchCategories,
  type CategoryGroupOut,
  type CategoryOut,
} from "@/lib/api";

/** Value of the "no category" option when `noneLabel` is set. */
export const NO_CATEGORY = "none";

const LAST_GROUP_KEY = "olmenta-last-category-group";

function readLastGroup(): string | null {
  try {
    return globalThis.localStorage?.getItem(LAST_GROUP_KEY) ?? null;
  } catch {
    return null;
  }
}

function writeLastGroup(id: string): void {
  try {
    globalThis.localStorage?.setItem(LAST_GROUP_KEY, id);
  } catch {
    // Storage blocked: the next form just falls back to the first group.
  }
}

const norm = (s: string) => s.trim().toLocaleLowerCase("es");

export interface CategoryComboboxOption {
  value: string;
  label: string;
}

export interface CategoryComboboxProps {
  /** Category id, NO_CATEGORY, an extra option's value, or "" for nothing picked. */
  value: string;
  onChange: (value: string) => void;
  /** Offer "no category" with this label ("Ready to assign" / "Uncategorized"). */
  noneLabel?: string;
  /** Non-category choices listed after the categories (e.g. "Transfers →"). */
  extraGroups?: { heading: string; options: CategoryComboboxOption[] }[];
  placeholder?: string;
  size?: "md" | "sm";
  disabled?: boolean;
  ariaLabel?: string;
}

/* The one category picker (spec: category-picker): search across groups,
   "Create «X»" with a group choice, and the new category lands in the shared
   ["categories"] cache so every other open picker lists it at once.
   Archived categories and system groups (card payments) are never offered. */
export function CategoryCombobox({
  value,
  onChange,
  noneLabel,
  extraGroups = [],
  placeholder = "Select category",
  size = "md",
  disabled = false,
  ariaLabel = "Category",
}: Readonly<CategoryComboboxProps>) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");
  // Non-null while the inline creation form is shown.
  const [draftName, setDraftName] = React.useState<string | null>(null);

  const { data: groups } = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });
  const pickable = React.useMemo(
    () =>
      (groups ?? [])
        .filter((g) => !g.system)
        .map((g) => ({ ...g, categories: g.categories.filter((c) => !c.archived) })),
    [groups],
  );

  const selectedLabel = React.useMemo(() => {
    if (value === NO_CATEGORY && noneLabel) return noneLabel;
    for (const g of extraGroups) {
      const hit = g.options.find((o) => o.value === value);
      if (hit) return hit.label;
    }
    // Any category, archived included: an old row keeps showing its name.
    for (const g of groups ?? []) {
      const hit = g.categories.find((c) => c.id === value);
      if (hit) return hit.name;
    }
    return null;
  }, [value, noneLabel, extraGroups, groups]);

  const query = norm(search);
  const exactMatch = pickable.some((g) => g.categories.some((c) => norm(c.name) === query));

  function close() {
    setOpen(false);
    setSearch("");
    setDraftName(null);
  }

  function pick(next: string) {
    onChange(next);
    close();
  }

  const isMd = size === "md";
  return (
    <Popover
      open={open}
      onOpenChange={(next) => (next ? setOpen(true) : close())}
      // Modal: scrolling the list works inside dialogs.
      modal
    >
      <PopoverTrigger asChild disabled={disabled}>
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label={ariaLabel}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
            width: "100%",
            height: isMd ? 48 : 36,
            padding: isMd ? "0 14px" : "0 10px",
            borderRadius: isMd ? 10 : 8,
            border: `${isMd ? 1.5 : 1}px solid var(--border-hairline)`,
            background: disabled ? "var(--gray-100)" : "var(--surface)",
            color: selectedLabel ? "var(--text-strong)" : "var(--text-subtle)",
            font: `500 ${isMd ? 14 : 12}px var(--font-sans)`,
            cursor: disabled ? "not-allowed" : "pointer",
            textAlign: "left",
            minWidth: 0,
          }}
        >
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {selectedLabel ?? (groups ? placeholder : "Loading categories…")}
          </span>
          <Icon name="chevron-down" size={isMd ? 16 : 14} color="var(--text-subtle)" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="p-0 min-w-[260px] w-[var(--radix-popover-trigger-width)]"
        style={{
          borderRadius: "var(--r-md)",
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-lg)",
        }}
      >
        {draftName !== null ? (
          <CreateCategoryForm
            initialName={draftName}
            groups={pickable}
            onCancel={() => setDraftName(null)}
            onCreated={(id) => pick(id)}
          />
        ) : (
          <Command
            // Substring match on the name, not fuzzy (spec: matching anywhere).
            filter={(itemValue, term, keywords) => {
              if (itemValue === "__create") return 1;
              // Names live in keywords; values are ids, never searched.
              const hay = norm((keywords?.length ? keywords : [itemValue]).join(" "));
              return hay.includes(norm(term)) ? 1 : 0;
            }}
          >
            <CommandInput
              placeholder="Search or create…"
              value={search}
              onValueChange={setSearch}
            />
            <CommandList>
              {/* With a query and no exact match, "Create «X»" is the answer. */}
              {(!query || exactMatch) && <CommandEmpty>No matching category</CommandEmpty>}
              {noneLabel && (
                <CommandGroup>
                  <CommandItem value={noneLabel} onSelect={() => pick(NO_CATEGORY)}>
                    {noneLabel}
                  </CommandItem>
                </CommandGroup>
              )}
              {pickable.map((g) =>
                g.categories.length === 0 ? null : (
                  <CommandGroup key={g.id} heading={g.name}>
                    {g.categories.map((c) => (
                      <CommandItem
                        key={c.id}
                        value={c.id}
                        keywords={[c.name]}
                        onSelect={() => pick(c.id)}
                      >
                        <span style={{ flex: 1 }}>{c.name}</span>
                        {c.id === value && <Icon name="check" size={14} color="var(--brand)" />}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                ),
              )}
              {extraGroups.map((g) => (
                <CommandGroup key={g.heading} heading={g.heading}>
                  {g.options.map((o) => (
                    <CommandItem key={o.value} value={o.value} keywords={[o.label]} onSelect={() => pick(o.value)}>
                      {o.label}
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))}
              {query && !exactMatch && (
                <>
                  <CommandSeparator alwaysRender />
                  {/* forceMount on the group too: cmdk hides groups whose
                      items all fail the filter, forced items included. */}
                  <CommandGroup forceMount>
                    <CommandItem
                      value="__create"
                      forceMount
                      onSelect={() => setDraftName(search.trim())}
                    >
                      <Icon name="plus" size={14} color="var(--brand)" />
                      <span style={{ color: "var(--violet-700)", fontWeight: 600 }}>
                        Create «{search.trim()}»
                      </span>
                    </CommandItem>
                  </CommandGroup>
                </>
              )}
            </CommandList>
          </Command>
        )}
      </PopoverContent>
    </Popover>
  );
}

function CreateCategoryForm({
  initialName,
  groups,
  onCancel,
  onCreated,
}: Readonly<{
  initialName: string;
  groups: CategoryGroupOut[];
  onCancel: () => void;
  onCreated: (id: string) => void;
}>) {
  const [name, setName] = React.useState(initialName);
  const [groupId, setGroupId] = React.useState(() => {
    const last = readLastGroup();
    return groups.some((g) => g.id === last) ? (last as string) : (groups[0]?.id ?? "");
  });
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => createCategory({ name: name.trim(), group_id: groupId }),
    onSuccess: (created: CategoryOut) => {
      // Into the shared cache first: every open picker lists it this render.
      queryClient.setQueryData<CategoryGroupOut[]>(["categories"], (old) =>
        old?.map((g) =>
          g.id === groupId ? { ...g, categories: [...g.categories, created] } : g,
        ),
      );
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      writeLastGroup(groupId);
      onCreated(created.id);
    },
    onError: async (error) => {
      // Already there: pick the existing one instead of failing.
      if (error instanceof ApiError && error.code === "category_exists") {
        const fresh = await queryClient.fetchQuery({
          queryKey: ["categories"],
          queryFn: fetchCategories,
        });
        const existing = fresh
          .find((g) => g.id === groupId)
          ?.categories.find((c) => norm(c.name) === norm(name));
        if (existing) {
          writeLastGroup(groupId);
          onCreated(existing.id);
        }
      }
    },
  });

  const canSubmit = !!name.trim() && !!groupId && !mutation.isPending;
  const failed =
    mutation.isError &&
    !(mutation.error instanceof ApiError && mutation.error.code === "category_exists");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        // Inside dialogs: never submit the surrounding form.
        e.stopPropagation();
        if (canSubmit) mutation.mutate();
      }}
      style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}
    >
      <span className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>
        New category
      </span>
      <input
        aria-label="Category name"
        autoFocus
        value={name}
        maxLength={80}
        onChange={(e) => setName(e.target.value)}
        style={fieldStyle}
      />
      <select
        aria-label="Category group"
        value={groupId}
        onChange={(e) => setGroupId(e.target.value)}
        style={fieldStyle}
      >
        {groups.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name}
          </option>
        ))}
      </select>
      {failed && (
        <span role="alert" style={{ font: "600 12px var(--font-sans)", color: "var(--expense)" }}>
          That didn&apos;t save — try again.
        </span>
      )}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <Button variant="ghost" size="sm" type="button" onClick={onCancel}>
          Back
        </Button>
        <Button variant="primary" size="sm" type="submit" iconLeft="plus" disabled={!canSubmit}>
          {mutation.isPending ? "Creating…" : "Create category"}
        </Button>
      </div>
    </form>
  );
}

const fieldStyle: React.CSSProperties = {
  height: 38,
  padding: "0 10px",
  borderRadius: 8,
  border: "1.5px solid var(--border-hairline)",
  background: "var(--surface)",
  font: "500 14px var(--font-sans)",
  color: "var(--text-strong)",
  outline: "none",
};
