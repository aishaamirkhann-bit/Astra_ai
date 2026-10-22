import PageShell from "@/components/PageShell";
import PayloadSimulator from "@/components/b2b/PayloadSimulator";
import BuyerBiddingBoard from "@/components/b2b/BuyerBiddingBoard";

export default function B2bSourcingPage() {
  return <PageShell active="B2B Adapter" title="B2B Sourcing & Distribution" subtitle="Publish wholesale requests, compare AI-ranked supplier quotes, and keep distribution records transparent.">
    <BuyerBiddingBoard />
    <details className="rounded-xl border border-base-700 bg-base-900/40 p-4">
      <summary className="cursor-pointer text-xs font-semibold text-ink-300">Developer tools: UCP / ACP consent adapter</summary>
      <div className="mt-4"><PayloadSimulator /></div>
    </details>
  </PageShell>;
}
