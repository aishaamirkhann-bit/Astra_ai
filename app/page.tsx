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

export default function HomePage() {
  return (
    <div className="mx-auto flex max-w-[1600px]">
      <Sidebar active="Home" />

      <div className="flex-1">
        <TopBar />

        <main className="grid grid-cols-1 gap-5 p-4 lg:grid-cols-[1fr_320px] lg:p-8">
          {/* ── Center column ─────────────────────────────────────── */}
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_260px]">
              <HeroBanner />
              <AstraCheckWidget />
            </div>

            <ProductGrid />
            <PipelineBar />
          </div>

          {/* ── Right rail ────────────────────────────────────────── */}
          <div className="flex flex-col gap-5">
            <AiAssistantWidget />
            <HumanApprovalWidget />
            <VoiceWidget />
            <GoalsWalletRail />
          </div>
        </main>
      </div>
    </div>
  );
}
