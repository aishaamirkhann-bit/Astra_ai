import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import HeroBanner from "@/components/HeroBanner";
import AstraCheckWidget from "@/components/AstraCheckWidget";
import AiAssistantWidget from "@/components/AiAssistantWidget";
import HumanApprovalWidget from "@/components/HumanApprovalWidget";
import ProductGrid from "@/components/ProductGrid";
import PipelineBar from "@/components/PipelineBar";
import VoiceWidget from "@/components/VoiceWidget";
import GoalsWalletRail from "@/components/GoalsWalletRail";
import { getHomePage } from "@/lib/api";

// Server component — one round-trip to FastAPI's /api/v1/home hydrates the
// entire page, then every widget below gets its slice via props. No mock
// data, no client-side fetching waterfall.
export default async function HomePage() {
  const data = await getHomePage();

  return (
    <div className="mx-auto flex max-w-[1600px]">
      <Sidebar active="Home" />

      <div className="flex-1">
        <TopBar unreadNotifications={data.unread_notifications} />

        <main className="grid grid-cols-1 gap-5 p-4 lg:grid-cols-[1fr_320px] lg:p-8">
          {/* ── Center column ─────────────────────────────────────── */}
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_260px]">
              <HeroBanner suggestions={data.hero_suggestions} />
              <AstraCheckWidget astraCheck={data.astra_check} />
            </div>

            <ProductGrid products={data.recommended_products} />
            <PipelineBar pipeline={data.pipeline} />
          </div>

          {/* ── Right rail ────────────────────────────────────────── */}
          <div className="flex flex-col gap-5">
            <AiAssistantWidget suggestion={data.ai_assistant} />
            <HumanApprovalWidget approval={data.approval} />
            <VoiceWidget />
            <GoalsWalletRail data={data.goals_wallet} />
          </div>
        </main>
      </div>
    </div>
  );
}
