"use client";

import React from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type {
  OnboardingFinalizePayload,
  OnboardingProposal,
  OnboardingProposedAccount,
} from "@/lib/api";

export interface ReviewScreenProps {
  proposal: OnboardingProposal;
  submitting: boolean;
  onConfirm: (payload: OnboardingFinalizePayload) => void;
}

interface EditableItem {
  name: string;
  icon: string;
  checked: boolean;
}

interface EditableAccount {
  name: string;
  type: OnboardingProposedAccount["type"];
  checked: boolean;
}

const ACCOUNT_TYPES = [
  { value: "bank", label: "Bank" },
  { value: "credit", label: "Card" },
];

interface EditableGroup {
  name: string;
  checked: boolean;
  categories: EditableItem[];
}

const rowFont: React.CSSProperties = {
  font: "500 15px var(--font-sans)",
  color: "var(--text-strong)",
};

/* A checkbox + rename-in-place row, shared by categories and payees. */
function EditableRow({
  item,
  onToggle,
  onRename,
  indent = 0,
}: Readonly<{
  item: { name: string; checked: boolean };
  onToggle: () => void;
  onRename: (name: string) => void;
  indent?: number;
}>) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        paddingLeft: indent,
        opacity: item.checked ? 1 : 0.45,
      }}
    >
      <input
        type="checkbox"
        checked={item.checked}
        onChange={onToggle}
        style={{ width: 17, height: 17, accentColor: "var(--brand)", flex: "none" }}
      />
      <input
        value={item.name}
        onChange={(event) => onRename(event.target.value)}
        style={{
          ...rowFont,
          flex: 1,
          minWidth: 0,
          border: "none",
          outline: "none",
          background: "transparent",
          borderBottom: "1px dashed transparent",
        }}
        onFocus={(event) =>
          (event.target.style.borderBottom = "1px dashed var(--brand)")
        }
        onBlur={(event) => (event.target.style.borderBottom = "1px dashed transparent")}
      />
    </div>
  );
}

function AddNewButton({ label, onClick }: Readonly<{ label: string; onClick: () => void }>) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        border: "none",
        background: "transparent",
        cursor: "pointer",
        font: "600 13.5px var(--font-sans)",
        color: "var(--brand)",
        padding: "4px 0",
      }}
    >
      <Icon name="plus" size={15} />
      {label}
    </button>
  );
}

/* Post-interview verification: everything the AI proposed, editable before
   anything is persisted (spec: review before anything is created). */
export function ReviewScreen({ proposal, submitting, onConfirm }: ReviewScreenProps) {
  const [accounts, setAccounts] = React.useState<EditableAccount[]>(() =>
    (proposal.accounts ?? []).map((account) => ({ ...account, checked: true })),
  );
  const updateAccount = (index: number, patch: Partial<EditableAccount>) =>
    setAccounts((prev) => prev.map((a, i) => (i === index ? { ...a, ...patch } : a)));
  const [groups, setGroups] = React.useState<EditableGroup[]>(() =>
    proposal.category_groups.map((group) => ({
      name: group.name,
      checked: true,
      categories: group.categories.map((category) => ({
        name: category.name,
        icon: category.icon,
        checked: true,
      })),
    })),
  );
  const [payers, setPayers] = React.useState<EditableItem[]>(() =>
    proposal.payers.map((name) => ({ name, icon: "circle", checked: true })),
  );
  const [payees, setPayees] = React.useState<EditableItem[]>(() =>
    proposal.payees.map((name) => ({ name, icon: "circle", checked: true })),
  );

  const updateGroup = (index: number, patch: Partial<EditableGroup>) =>
    setGroups((prev) => prev.map((g, i) => (i === index ? { ...g, ...patch } : g)));

  const updateCategory = (
    groupIndex: number,
    categoryIndex: number,
    patch: Partial<EditableItem>,
  ) =>
    setGroups((prev) =>
      prev.map((group, gi) =>
        gi === groupIndex
          ? {
              ...group,
              categories: group.categories.map((category, ci) =>
                ci === categoryIndex ? { ...category, ...patch } : category,
              ),
            }
          : group,
      ),
    );

  const buildPayload = (): OnboardingFinalizePayload => ({
    accounts: accounts
      .filter((account) => account.checked && account.name.trim())
      .map((account) => ({ name: account.name.trim(), type: account.type })),
    category_groups: groups
      .filter((group) => group.checked)
      .map((group) => ({
        name: group.name.trim(),
        categories: group.categories
          .filter((category) => category.checked && category.name.trim())
          .map((category) => ({ name: category.name.trim(), icon: category.icon })),
      }))
      .filter((group) => group.name && group.categories.length > 0),
    payers: payers
      .filter((item) => item.checked && item.name.trim())
      .map((item) => item.name.trim()),
    payees: payees
      .filter((item) => item.checked && item.name.trim())
      .map((item) => item.name.trim()),
    income: proposal.income,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Panel title="Your accounts">
        <p style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", margin: "0 0 14px" }}>
          Where your money sits. Each card gets its own line in the budget to
          set aside what you&apos;ll pay it.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {accounts.map((account, index) => (
            <div
              key={`account-${index}`}
              style={{ display: "flex", alignItems: "center", gap: 10 }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <EditableRow
                  item={account}
                  onToggle={() => updateAccount(index, { checked: !account.checked })}
                  onRename={(name) => updateAccount(index, { name })}
                />
              </div>
              {account.checked && (
                <SegmentedControl
                  size="sm"
                  options={ACCOUNT_TYPES}
                  value={account.type}
                  onChange={(type) =>
                    updateAccount(index, { type: type as EditableAccount["type"] })
                  }
                />
              )}
            </div>
          ))}
        </div>
        <AddNewButton
          label="Add account"
          onClick={() =>
            setAccounts((prev) => [...prev, { name: "New account", type: "bank", checked: true }])
          }
        />
      </Panel>

      <Panel title="Your categories">
        <p style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", margin: "0 0 14px" }}>
          Built from your answers. Uncheck what you don&apos;t need, click a name
          to rename it.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {groups.map((group, groupIndex) => (
            <div key={`group-${groupIndex}-${group.categories.length}`} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontWeight: 700 }}>
                <EditableRow
                  item={group}
                  onToggle={() => updateGroup(groupIndex, { checked: !group.checked })}
                  onRename={(name) => updateGroup(groupIndex, { name })}
                />
              </div>
              {group.checked &&
                group.categories.map((category, categoryIndex) => (
                  <EditableRow
                    key={`cat-${groupIndex}-${categoryIndex}`}
                    item={category}
                    indent={26}
                    onToggle={() =>
                      updateCategory(groupIndex, categoryIndex, {
                        checked: !category.checked,
                      })
                    }
                    onRename={(name) => updateCategory(groupIndex, categoryIndex, { name })}
                  />
                ))}
              {group.checked && (
                <div style={{ paddingLeft: 26 }}>
                  <AddNewButton
                    label="Add category"
                    onClick={() =>
                      updateGroup(groupIndex, {
                        categories: [
                          ...group.categories,
                          { name: "New category", icon: "circle", checked: true },
                        ],
                      })
                    }
                  />
                </div>
              )}
            </div>
          ))}
        </div>
        <AddNewButton
          label="Add group"
          onClick={() =>
            setGroups((prev) => [
              ...prev,
              { name: "New group", checked: true, categories: [] },
            ])
          }
        />
      </Panel>

      <Panel title="Who pays you">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {payers.map((item, index) => (
            <EditableRow
              key={`payer-${index}`}
              item={item}
              onToggle={() =>
                setPayers((prev) =>
                  prev.map((p, i) => (i === index ? { ...p, checked: !p.checked } : p)),
                )
              }
              onRename={(name) =>
                setPayers((prev) => prev.map((p, i) => (i === index ? { ...p, name } : p)))
              }
            />
          ))}
        </div>
        <AddNewButton
          label="Add payer"
          onClick={() =>
            setPayers((prev) => [...prev, { name: "New payer", icon: "circle", checked: true }])
          }
        />
      </Panel>

      <Panel title="Who you pay">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {payees.map((item, index) => (
            <EditableRow
              key={`payee-${index}`}
              item={item}
              onToggle={() =>
                setPayees((prev) =>
                  prev.map((p, i) => (i === index ? { ...p, checked: !p.checked } : p)),
                )
              }
              onRename={(name) =>
                setPayees((prev) => prev.map((p, i) => (i === index ? { ...p, name } : p)))
              }
            />
          ))}
        </div>
        <AddNewButton
          label="Add payee"
          onClick={() =>
            setPayees((prev) => [...prev, { name: "New payee", icon: "circle", checked: true }])
          }
        />
      </Panel>

      <Button
        size="lg"
        block
        iconLeft="check"
        disabled={submitting}
        onClick={() => onConfirm(buildPayload())}
      >
        {submitting ? "Setting up…" : "Create my budget"}
      </Button>
    </div>
  );
}
