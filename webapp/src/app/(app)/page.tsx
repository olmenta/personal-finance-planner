import { ConversationView } from "@/components/chat/ConversationView";
import { HistorySheet } from "@/components/chat/HistorySheet";
import { Icon } from "@/components/ui/Icon";
import Link from "next/link";

/* Home (spec: home, coach-conversation): your conversation with Olmenta.
   The month arrives as a coach message on every visit; questions, recorded
   expenses and confirmed changes stay in the history. */
export default function HomePage() {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          padding: "22px 28px 14px",
          maxWidth: 1088,
          width: "100%",
          margin: "0 auto",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <h1 style={{ font: "700 28px var(--font-sans)", letterSpacing: "-0.8px", color: "var(--text-strong)" }}>Home</h1>
          <div style={{ font: "500 14.5px var(--font-sans)", color: "var(--text-muted)", marginTop: 2 }}>
            Your conversation with Olmenta
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <HistorySheet />
          <Link href="/settings" className="app-topbar-mobile" aria-label="Settings" style={{ color: "var(--text-muted)", padding: 6 }}>
            <Icon name="settings" size={20} />
          </Link>
        </div>
      </header>
      <ConversationView />
    </div>
  );
}
