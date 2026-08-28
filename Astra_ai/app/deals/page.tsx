import Link from "next/link";
import { Star, ShieldCheck, Tag } from "lucide-react";
import PageShell from "@/components/PageShell";
import { PRODUCTS } from "@/lib/mockData";

export default function DealsPage() {
  const deals = PRODUCTS.filter((p) => p.tag);

  return (
    <PageShell
      active="Deals"
      title="Deals"
      subtitle="Listings the Trust Agent has flagged as priced below the market average."
    >
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
        {deals.map((p) => (
          <Link
            key={p.slug}
            href={`/product/${p.slug}`}
            className="glass glass-hover block rounded-xl2 p-3"
          >
            <div
              className="photo-frame relative mb-3 aspect-square rounded-lg"
              style={{ backgroundImage: `url(${p.image})` }}
            >
              <span className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-astra-gradient px-2 py-0.5 text-[9px] font-semibold text-white">
                <Tag className="h-2.5 w-2.5" /> {p.tag}
              </span>
            </div>
            <p className="truncate text-xs font-medium text-ink-100">{p.name}</p>
            <div className="mt-1 flex items-center justify-between">
              <div className="flex items-center gap-1 text-[10px] text-ink-500">
                <Star className="h-3 w-3 fill-signal-hold text-signal-hold" />
                {p.rating}
              </div>
              <div className="flex items-center gap-0.5 text-[10px] text-signal-good">
                <ShieldCheck className="h-3 w-3" />
                {p.trust}
              </div>
            </div>
            <p className="mt-1 font-display text-sm font-semibold text-ink-100">{p.price}</p>
          </Link>
        ))}
      </div>
    </PageShell>
  );
}
