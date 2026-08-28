import Link from "next/link";
import { ArrowRight } from "lucide-react";
import PageShell from "@/components/PageShell";
import { CATEGORIES } from "@/lib/mockData";

export default function CategoriesPage() {
  return (
    <PageShell
      active="Categories"
      title="Categories"
      subtitle="Browse the full catalog — from electronics to fashion, jewelry, and beauty."
    >
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
        {CATEGORIES.map((c) => (
          <Link
            key={c.slug}
            href={`/explore?category=${encodeURIComponent(c.name)}`}
            className="glass glass-hover group overflow-hidden rounded-xl2"
          >
            <div
              className="photo-frame aspect-[4/3]"
              style={{ backgroundImage: `url(${c.image})` }}
            />
            <div className="flex items-center justify-between p-4">
              <div>
                <p className="text-sm font-medium text-ink-100">{c.name}</p>
                <p className="text-[11px] text-ink-500">{c.count} listings</p>
              </div>
              <ArrowRight className="h-4 w-4 text-ink-500 transition-transform group-hover:translate-x-0.5 group-hover:text-astra-cyan" />
            </div>
          </Link>
        ))}
      </div>
    </PageShell>
  );
}
