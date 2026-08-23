import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";

export default function PageShell({
  active,
  title,
  subtitle,
  children,
}: {
  active: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mx-auto flex max-w-[1600px]">
      <Sidebar active={active} />
      <div className="min-w-0 flex-1">
        <TopBar />
        <main className="flex min-w-0 flex-col gap-6 p-4 lg:p-8">
          <div>
            <h1 className="font-display text-xl font-semibold text-ink-100">{title}</h1>
            <p className="mt-1 text-sm text-ink-500">{subtitle}</p>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
