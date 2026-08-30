import PageShell from "@/components/PageShell";
import MessagesClient from "@/components/messages/MessagesClient";

export default function MessagesPage() {
  return (
    <PageShell
      active="Messages"
      title="Messages"
      subtitle="Your ASTRA Voice Copilot history — every conversation, in English or Roman Urdu."
    >
      <MessagesClient />
    </PageShell>
  );
}
