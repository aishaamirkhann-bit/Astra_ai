import PageShell from "@/components/PageShell";
import BudgetAgentDashboard from "@/components/goals/BudgetAgentDashboard";

export default function GoalsPage() {
  return (
    <PageShell
      active="My Goals"
      title="My Goals & Budget Agent"
      subtitle="Personal financial intelligence that matches high-trust deals to your goals and safe monthly budget."
    >
      <BudgetAgentDashboard />
    </PageShell>
  );
}
