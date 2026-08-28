import PageShell from "@/components/PageShell";
import GoalManager from "@/components/goals/GoalManager";
import AffordabilityAnalyzer from "@/components/goals/AffordabilityAnalyzer";

export default function GoalsPage() {
  return (
    <PageShell
      active="My Goals"
      title="Goals & Wallet"
      subtitle="The Rupee Intelligence Engine — plan savings and check affordability before you buy."
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_380px]">
        <GoalManager />
        <AffordabilityAnalyzer />
      </div>
    </PageShell>
  );
}
