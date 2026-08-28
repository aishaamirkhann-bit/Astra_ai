import PageShell from "@/components/PageShell";
import PayloadSimulator from "@/components/b2b/PayloadSimulator";

export default function B2bAdapterPage() {
  return (
    <PageShell
      active="B2B Adapter"
      title="B2B Adapter Mode"
      subtitle="Developer view — simulate UCP / ACP payloads against the ASTRA consent adapter."
    >
      <PayloadSimulator />
    </PageShell>
  );
}
