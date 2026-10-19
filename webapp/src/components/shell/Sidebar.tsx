"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { useCurrentUser } from "./CurrentUser";

const items = [
  { href: "/", icon: "home", label: "Home" },
  { href: "/budgets", icon: "pie-chart", label: "Budget" },
  { href: "/transactions", icon: "receipt", label: "Transactions" },
  { href: "/future", icon: "calendar", label: "Future" },
  { href: "/accounts", icon: "wallet", label: "Accounts" },
];

/* The five destinations, then Settings and the user (spec: navigation,
   mockup redesign.png). Screens reached from one keep it highlighted: What
   you owe lives under Accounts. */
export function isActive(href: string, pathname: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/accounts" && pathname.startsWith("/debts")) return true;
  return pathname === href || pathname.startsWith(`${href}/`);
}

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
      aria-current={active ? "page" : undefined}
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
  const user = useCurrentUser();

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

      <nav aria-label="Main" style={{ display: "flex", flexDirection: "column", gap: 3, marginTop: 30 }}>
        {items.map((it) => (
          <SideItem key={it.href} {...it} active={isActive(it.href, pathname)} />
        ))}
      </nav>

      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
        <SideItem href="/settings" icon="settings" label="Settings" active={isActive("/settings", pathname)} />
        <Link
          href="/settings"
          aria-label="Your profile"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 11,
            padding: "8px 6px",
            textDecoration: "none",
          }}
        >
          <Avatar name={user.name} src={user.picture ?? undefined} size={40} />
          <div style={{ flex: 1, minWidth: 0 }} data-testid="sidebar-user">
            <div style={{ font: "700 13.5px var(--font-sans)", color: "var(--text-strong)" }}>
              {user.name}
            </div>
            {user.email && (
              <div
                style={{
                  font: "500 12px var(--font-sans)",
                  color: "var(--text-muted)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {user.email}
              </div>
            )}
          </div>
          <Icon name="chevron-right" size={18} color="var(--text-subtle)" />
        </Link>
      </div>
    </aside>
  );
}
