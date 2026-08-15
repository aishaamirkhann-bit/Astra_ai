import PageShell from "@/components/PageShell";
import RulesVsLlmPanel from "@/components/astra-check/RulesVsLlmPanel";
import ContradictionMonitor from "@/components/astra-check/ContradictionMonitor";
import TrustInspectionPanel from "@/components/astra-check/TrustInspectionPanel";

export default function AstraCheckPage() {
  return (
    <PageShell
      active="ASTRA Check"
      title="ASTRA Check"
      subtitle="The trust and financial-intelligence engine behind every buy verdict."
    >
      <RulesVsLlmPanel />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ContradictionMonitor />
        <TrustInspectionPanel />
      </div>
    </PageShell>
  );
}
