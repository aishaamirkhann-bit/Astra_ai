import Link from "next/link";
import { Star, ShieldCheck, SearchX } from "lucide-react";
import type { Product } from "@/lib/mockData";

export default function HybridResultsGrid({ products }: { products: readonly Product[] }) {
  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs text-ink-500">
          <span className="font-semibold text-ink-100">{products.length}</span> results ·
          blending keyword + semantic match
        </p>
        <select className="rounded-lg border border-base-600 bg-base-800 px-2.5 py-1.5 text-[11px] text-ink-300">
          <option>Most relevant</option>
          <option>Price: low to high</option>
          <option>Trust score</option>
        </select>
      </div>

      {products.length === 0 ? (
        <div className="glass flex flex-col items-center gap-2 rounded-xl2 p-10 text-center">
          <SearchX className="h-6 w-6 text-ink-500" />
          <p className="text-sm font-medium text-ink-100">No matches yet</p>
          <p className="text-xs text-ink-500">Try a different search term, category, or a higher price cap.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
          {products.map((p) => (
            <Link
              key={p.slug}
              href={`/product/${p.slug}`}
              className="glass glass-hover block rounded-xl2 p-3"
            >
              <div
                className="photo-frame relative mb-3 aspect-square rounded-lg"
                style={{ backgroundImage: `url(${p.image})` }}
              >
                {p.tag && (
                  <span className="absolute left-2 top-2 rounded-full bg-astra-gradient px-2 py-0.5 text-[9px] font-semibold text-white">
                    {p.tag}
                  </span>
                )}
              </div>
              <p className="truncate text-xs font-medium text-ink-100">{p.name}</p>
              <div className="mt-1 flex items-center justify-between">
                <div className="flex items-center gap-1 text-[10px] text-ink-500">
                  <Star className="h-3 w-3 fill-signal-hold text-signal-hold" />
                  {p.rating}
                </div>
                <div className="flex items-center gap-1 text-[10px] text-signal-good">
                  <ShieldCheck className="h-3 w-3" />
                  {p.trust}
                </div>
              </div>
              <p className="mt-1 font-display text-sm font-semibold text-ink-100">{p.price}</p>
              <p className="truncate text-[10px] text-ink-500">{p.seller}</p>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
