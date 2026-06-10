"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";

const items = [
  { href: "/", icon: "dashboard", label: "Overview" },
  { href: "/transactions", icon: "receipt", label: "Transactions" },
  { href: "/budgets", icon: "pie-chart", label: "Budgets" },
  { href: "/goals", icon: "target", label: "Goals" },
  { href: "/coach", icon: "sparkles", label: "Coach" },
];

function SideItem({
  href,
  icon,
  label,
  active,
}: {
  href: string;
  icon: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        width: "100%",
        textAlign: "left",
        padding: "11px 13px",
        borderRadius: "var(--r-md)",
        textDecoration: "none",
        background: active ? "var(--violet-100)" : "transparent",
        color: active ? "var(--violet-700)" : "var(--text-muted)",
        font: `${active ? 700 : 600} 14.5px var(--font-sans)`,
        letterSpacing: "-0.1px",
        transition:
          "background var(--dur-base) var(--ease-out), color var(--dur-base) var(--ease-out)",
      }}
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.background = "var(--violet-50)";
          e.currentTarget.style.color = "var(--text-body)";
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = "var(--text-muted)";
        }
      }}
    >
      <Icon name={icon} size={20} strokeWidth={active ? 2.4 : 2} />
      {label}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="app-sidebar"
      style={{
        width: "var(--sidebar-w)",
        flex: "none",
        background: "var(--surface)",
        borderRight: "1px solid var(--border-hairline)",
        padding: "22px 16px",
        flexDirection: "column",
        height: "100%",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "4px 8px 0" }}>
        <Image src="/brand/olmenta-mark.svg" width={34} height={34} alt="Olmenta" />
        <span
          style={{
            font: "800 21px var(--font-sans)",
            letterSpacing: "-1px",
            color: "var(--ink-900)",
          }}
        >
          Olmenta
        </span>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 3, marginTop: 26 }}>
        <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", padding: "0 13px 8px" }}>
          Menu
        </div>
        {items.map((it) => (
          <SideItem key={it.href} {...it} active={pathname === it.href} />
        ))}
      </nav>

      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 14 }}>
        <div
          style={{
            background: "var(--grad-coach)",
            borderRadius: "var(--r-xl)",
            padding: 16,
            color: "#fff",
          }}
        >
          <span
            style={{
              display: "inline-flex",
              width: 30,
              height: 30,
              borderRadius: "var(--r-sm)",
              background: "rgba(255,255,255,.1)",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 10,
            }}
          >
            <Icon name="sparkles" size={16} color="var(--mint-400)" />
          </span>
          <div style={{ font: "700 14.5px var(--font-sans)", letterSpacing: "-0.2px" }}>
            Olmenta Pro
          </div>
          <div
            style={{
              font: "500 12.5px/1.45 var(--font-sans)",
              color: "rgba(255,255,255,.7)",
              margin: "4px 0 12px",
            }}
          >
            Deeper coaching, unlimited goals.
          </div>
          <button
            type="button"
            style={{
              width: "100%",
              background: "#fff",
              color: "var(--ink-900)",
              border: "none",
              borderRadius: 999,
              padding: "9px",
              font: "600 13.5px var(--font-sans)",
              cursor: "pointer",
            }}
          >
            Upgrade
          </button>
        </div>
        <Link
          href="/settings"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 11,
            padding: "8px 6px",
            textDecoration: "none",
          }}
        >
          <Avatar name="Maya Ortiz" size={38} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ font: "700 13.5px var(--font-sans)", color: "var(--text-strong)" }}>
              Maya Ortiz
            </div>
            <div
              style={{
                font: "500 12px var(--font-sans)",
                color: "var(--text-muted)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              maya@olmenta.app
            </div>
          </div>
          <Icon name="settings" size={18} color="var(--text-subtle)" />
        </Link>
      </div>
    </aside>
  );
}
