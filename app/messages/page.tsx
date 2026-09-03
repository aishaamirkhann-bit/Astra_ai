import PageShell from "@/components/PageShell";
import MessagesClient from "@/components/messages/MessagesClient";
import DirectMessagesPanel from "@/components/messaging/DirectMessagesPanel";

export default function MessagesPage() {
  return (
    <PageShell
      active="Messages"
      title="Messages"
      subtitle="Your ASTRA Voice Copilot history and direct buyer-seller conversations."
    >
      <div className="flex flex-col gap-6">
        <MessagesClient />
        <DirectMessagesPanel />
      </div>
    </PageShell>
  );
}
