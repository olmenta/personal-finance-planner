import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconChip } from "@/components/ui/IconChip";
import { Panel } from "@/components/ui/Panel";
import { TopBar } from "@/components/shell/TopBar";
import { goals } from "@/lib/mock-data";

export default function GoalsPage() {
  return (
    <>
      <TopBar title="Goals" sub="Japan trip · 68% there" />
      <div className="app-content">
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button variant="primary" size="sm" iconLeft="plus">
            Add goal
          </Button>
        </div>
        <div className="grid-goals">
          {goals.map((g) => (
            <Panel key={g.label}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 16,
                }}
              >
                <IconChip icon={g.icon} tone={g.tone} size={46} />
                <Badge tone="neutral">{g.due}</Badge>
              </div>
              <div
                style={{
                  font: "700 17px var(--font-sans)",
                  letterSpacing: "-0.3px",
                  color: "var(--text-strong)",
                }}
              >
                {g.label}
              </div>
              <div
                style={{
                  font: "800 26px var(--font-sans)",
                  letterSpacing: "-0.8px",
                  color: "var(--text-strong)",
                  marginTop: 8,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {g.saved}
                <span style={{ font: "500 15px var(--font-sans)", color: "var(--text-subtle)" }}>
                  {" "}
                  / {g.target}
                </span>
              </div>
              <div
                style={{
                  height: 8,
                  borderRadius: "var(--r-full)",
                  background: "var(--gray-100)",
                  overflow: "hidden",
                  margin: "14px 0 8px",
                }}
              >
                <div
                  style={{
                    width: `${g.percent}%`,
                    height: "100%",
                    borderRadius: "var(--r-full)",
                    background: "var(--grad-balance)",
                  }}
                />
              </div>
              <div style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)" }}>
                {g.percent}% there — on track for {g.due === "Ongoing" ? "your target" : g.due}
              </div>
            </Panel>
          ))}
        </div>
      </div>
    </>
  );
}
