import { CoachConversation, CoachHeader } from "@/components/shell/CoachConversation";

export default function CoachPage() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        maxWidth: 760,
        margin: "0 auto",
        width: "100%",
        background: "var(--surface)",
        borderLeft: "1px solid var(--border-hairline)",
        borderRight: "1px solid var(--border-hairline)",
      }}
    >
      <CoachHeader note="Always here" />
      <CoachConversation />
    </div>
  );
}
