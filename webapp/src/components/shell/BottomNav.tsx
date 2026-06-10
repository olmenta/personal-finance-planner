"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";

const items = [
  { href: "/", icon: "home", label: "Home" },
  { href: "/budgets", icon: "pie-chart", label: "Report" },
  { href: "/coach", icon: "sparkles", label: "Coach" },
  { href: "/settings", icon: "settings", label: "Settings" },
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
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        minWidth: 56,
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
    <div className="app-bottomnav">
      {items.slice(0, 2).map((it) => (
        <NavItem key={it.href} {...it} active={pathname === it.href} />
      ))}
      <div style={{ width: 60, flex: "none" }} />
      {items.slice(2).map((it) => (
        <NavItem key={it.href} {...it} active={pathname === it.href} />
      ))}
      <div
        style={{
          position: "absolute",
          top: -18,
          left: "50%",
          transform: "translateX(-50%)",
        }}
      >
        <IconButton
          icon="plus"
          variant="fab"
          ariaLabel="Add transaction"
          onClick={() => router.push("/transactions")}
        />
      </div>
    </div>
  );
}
