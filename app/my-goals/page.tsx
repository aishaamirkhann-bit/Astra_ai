import BudgetAgentDashboard from "@/components/goals/BudgetAgentDashboard";
import PageShell from "@/components/PageShell";

export const metadata = { title: "My Goals & Budget Agent | Astra AI" };

export default function MyGoalsPage() {
  return (
    <PageShell active="My Goals" title="My Goals & Budget Agent" subtitle="Goal allocations, monthly budget progress, and verified deal savings in one canonical view.">
      <BudgetAgentDashboard />
    </PageShell>
  );
}
