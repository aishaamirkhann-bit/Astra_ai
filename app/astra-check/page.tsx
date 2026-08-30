import PageShell from "@/components/PageShell";
import AstraCheckDashboard from "@/components/astra-check/AstraCheckDashboard";

export default function AstraCheckPage() {
  return (
    <PageShell
      active="ASTRA Check"
      title="ASTRA Check"
      subtitle="Live seller verification, authenticity intelligence, price integrity, and Deals eligibility."
    >
      <AstraCheckDashboard />
    </PageShell>
  );
}
