"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";
import { isActive } from "./Sidebar";

const items = [
  { href: "/", icon: "home", label: "Home" },
  { href: "/budgets", icon: "pie-chart", label: "Budget" },
  { href: "/transactions", icon: "receipt", label: "Transactions" },
  { href: "/future", icon: "calendar", label: "Future" },
  { href: "/accounts", icon: "wallet", label: "Accounts" },
];

function NavItem({
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
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        minWidth: 48,
        textDecoration: "none",
      }}
    >
      <Icon
        name={icon}
        size={22}
        color={active ? "var(--violet-600)" : "var(--gray-400)"}
        strokeWidth={active ? 2.4 : 2}
      />
      <span
        style={{
          font: `${active ? 700 : 600} 11px var(--font-sans)`,
          color: active ? "var(--ink-900)" : "var(--gray-400)",
        }}
      >
        {label}
      </span>
    </Link>
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <nav className="app-bottomnav" aria-label="Main">
      {items.slice(0, 2).map((it) => (
        <NavItem key={it.href} {...it} active={isActive(it.href, pathname)} />
      ))}
      {/* The add button sits in the bar's flow, raised above it (five tabs). */}
      <div style={{ marginTop: -30, flex: "none" }}>
        <IconButton
          icon="plus"
          variant="fab"
          ariaLabel="Add transaction"
          onClick={() => router.push("/transactions")}
        />
      </div>
      {items.slice(2).map((it) => (
        <NavItem key={it.href} {...it} active={isActive(it.href, pathname)} />
      ))}
    </nav>
  );
}
