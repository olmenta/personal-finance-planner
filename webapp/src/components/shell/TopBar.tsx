"use client";

import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/shadcn/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/shadcn/tooltip";
import { Icon } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";
import { SearchInput } from "@/components/ui/SearchInput";

const MONTHS = [
  { value: "2026-06", label: "June 2026" },
  { value: "2026-05", label: "May 2026" },
  { value: "2026-04", label: "April 2026" },
  { value: "2026-03", label: "March 2026" },
  { value: "2026-02", label: "February 2026" },
  { value: "2026-01", label: "January 2026" },
];

const NOTIFICATIONS = [
  { id: 1, text: "You're 74% through your Food & dining budget.", time: "2h ago" },
  { id: 2, text: "Bills & utilities is over budget by 1%.", time: "Yesterday" },
  { id: 3, text: "Japan trip goal reached 68% — on track for October.", time: "3d ago" },
];

function NotificationBell() {
  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <span>
              <IconButton icon="bell" variant="ghost" ariaLabel="Notifications" />
            </span>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent side="bottom" style={{ borderRadius: "var(--r-xs)" }}>
          Notifications
        </TooltipContent>
      </Tooltip>

      <DropdownMenuContent
        align="end"
        style={{
          width: 320,
          borderRadius: "var(--r-xl)",
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-lg)",
          padding: "4px 0",
        }}
      >
        <DropdownMenuLabel
          style={{ font: "700 14px var(--font-sans)", padding: "12px 16px 8px" }}
        >
          Notifications
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {NOTIFICATIONS.map((n) => (
          <DropdownMenuItem
            key={n.id}
            style={{ padding: "10px 16px", cursor: "pointer" }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              <span
                style={{
                  font: "500 13.5px var(--font-sans)",
                  color: "var(--text-body)",
                  lineHeight: 1.45,
                }}
              >
                {n.text}
              </span>
              <span style={{ font: "500 11.5px var(--font-sans)", color: "var(--text-subtle)" }}>
                {n.time}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          style={{
            padding: "10px 16px",
            font: "600 13px var(--font-sans)",
            color: "var(--brand)",
            cursor: "pointer",
          }}
        >
          <Icon name="check" size={15} color="var(--brand)" />
          Mark all as read
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function TopBar({ title, sub }: Readonly<{ title: string; sub?: string }>) {
  const [month, setMonth] = React.useState("2026-06");

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "22px 28px",
        borderBottom: "1px solid var(--border-hairline)",
        background: "var(--surface)",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <h1
          style={{
            font: "700 24px var(--font-sans)",
            letterSpacing: "-0.6px",
            color: "var(--text-strong)",
          }}
        >
          {title}
        </h1>
        {sub && (
          <div
            style={{
              font: "500 13.5px var(--font-sans)",
              color: "var(--text-muted)",
              marginTop: 2,
            }}
          >
            {sub}
          </div>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div className="app-topbar-extras" style={{ alignItems: "center", gap: 12 }}>
          <div style={{ width: 240 }}>
            <SearchInput placeholder="Search transactions" />
          </div>

          <Select value={month} onValueChange={setMonth}>
            <SelectTrigger
              className="h-[38px] rounded-full border text-sm font-semibold gap-1.5 px-4 whitespace-nowrap"
              style={{
                borderColor: "var(--border-hairline)",
                background: "var(--surface)",
                color: "var(--text-body)",
                fontFamily: "var(--font-sans)",
                boxShadow: "var(--shadow-xs)",
              }}
            >
              <Icon name="calendar" size={15} color="var(--text-muted)" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent
              align="end"
              style={{
                borderRadius: "var(--r-md)",
                border: "1px solid var(--border-hairline)",
                boxShadow: "var(--shadow-lg)",
              }}
            >
              {MONTHS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <NotificationBell />
      </div>
    </header>
  );
}
