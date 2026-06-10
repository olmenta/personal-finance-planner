import React from "react";

export interface AvatarProps {
  src?: string;
  name?: string;
  size?: number;
  ring?: "none" | "brand" | "mint";
  badge?: React.ReactNode;
  style?: React.CSSProperties;
}

const rings: Record<string, string> = {
  none: "none",
  brand: "0 0 0 2.5px var(--surface), 0 0 0 4.5px var(--brand)",
  mint: "0 0 0 2.5px var(--surface), 0 0 0 4.5px var(--accent)",
};

export function Avatar({
  src,
  name = "",
  size = 44,
  ring = "none",
  badge,
  style,
}: AvatarProps) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  return (
    <span
      style={{ position: "relative", display: "inline-flex", flex: "none", ...style }}
    >
      <span
        style={{
          width: size,
          height: size,
          borderRadius: "var(--r-full)",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: src ? "var(--gray-100)" : "var(--violet-100)",
          color: "var(--violet-700)",
          fontFamily: "var(--font-sans)",
          fontWeight: 700,
          fontSize: size * 0.36,
          letterSpacing: "-0.3px",
          boxShadow: rings[ring] || rings.none,
        }}
      >
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={name}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          initials || "?"
        )}
      </span>
      {badge && (
        <span
          style={{
            position: "absolute",
            right: -2,
            bottom: -2,
            width: size * 0.42,
            height: size * 0.42,
            borderRadius: "var(--r-full)",
            background: "var(--accent)",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "2px solid var(--surface)",
          }}
        >
          {badge}
        </span>
      )}
    </span>
  );
}
