"use client";

import Link from "next/link";
import React from "react";
import { useAccounts } from "@/components/AccountPicker";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { IconChip, type ChipTone } from "@/components/ui/IconChip";
import { Switch } from "@/components/ui/Switch";
import { TopBar } from "@/components/shell/TopBar";
import { CategorySettings } from "@/components/CategorySettings";

function Row({
  icon,
  tone,
  label,
  sub,
  right,
  last = false,
}: {
  icon: string;
  tone: ChipTone;
  label: string;
  sub?: string;
  right?: React.ReactNode;
  last?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 13,
        padding: "13px 0",
        borderBottom: last ? "none" : "1px solid var(--border-hairline)",
      }}
    >
      <IconChip icon={icon} tone={tone} size={38} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            font: "600 15px var(--font-sans)",
            color: "var(--text-strong)",
            letterSpacing: "-0.1px",
          }}
        >
          {label}
        </div>
        {sub && (
          <div
            style={{
              font: "500 12.5px var(--font-sans)",
              color: "var(--text-muted)",
              marginTop: 1,
            }}
          >
            {sub}
          </div>
        )}
      </div>
      {right}
    </div>
  );
}

const groupStyle: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border-hairline)",
  borderRadius: "var(--r-xl)",
  padding: "4px 16px",
  boxShadow: "var(--shadow-sm)",
};

export default function SettingsPage() {
  const { active: accounts, isSuccess } = useAccounts();
  let accountsSub: string | undefined;
  if (isSuccess) accountsSub = accounts.length === 1 ? "1 account" : `${accounts.length} accounts`;
  return (
    <>
      <TopBar title="Settings" sub="Your profile, preferences and coach controls." />
      <div className="app-content" style={{ maxWidth: 720 }}>
        <div
          style={{
            ...groupStyle,
            padding: 18,
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <Avatar name="Maya Ortiz" ring="brand" size={56} />
          <div style={{ flex: 1 }}>
            <div
              style={{
                font: "700 17px var(--font-sans)",
                letterSpacing: "-0.3px",
                color: "var(--text-strong)",
              }}
            >
              Maya Ortiz
            </div>
            <div
              style={{
                font: "500 13px var(--font-sans)",
                color: "var(--text-muted)",
                marginTop: 1,
              }}
            >
              maya@olmenta.app
            </div>
          </div>
          <Badge tone="mint" icon="sparkles">
            Pro
          </Badge>
        </div>

        <div>
          <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", margin: "4px 2px 6px" }}>
            Coach
          </div>
          <div style={groupStyle}>
            <Row
              icon="sparkles"
              tone="violet"
              label="Proactive insights"
              sub="Let the coach reach out"
              right={<Switch defaultChecked />}
            />
            <Row
              icon="bell"
              tone="info"
              label="Spending nudges"
              sub="When you near a cap"
              right={<Switch defaultChecked />}
              last
            />
          </div>
        </div>

        <CategorySettings />

        <div>
          <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", margin: "4px 2px 6px" }}>
            Account
          </div>
          <div style={groupStyle}>
            <Link href="/accounts" style={{ display: "block", color: "inherit", textDecoration: "none" }}>
              <Row
                icon="wallet"
                tone="violet"
                label="Accounts & cards"
                sub={accountsSub}
                right={<Icon name="chevron-right" size={18} color="var(--text-subtle)" />}
              />
            </Link>
            <Row
              icon="target"
              tone="mint"
              label="Goals"
              sub="Japan trip · 68%"
              right={<Icon name="chevron-right" size={18} color="var(--text-subtle)" />}
            />
            <Row
              icon="lock"
              tone="neutral"
              label="Privacy & security"
              right={<Icon name="chevron-right" size={18} color="var(--text-subtle)" />}
              last
            />
          </div>
        </div>
      </div>
    </>
  );
}
