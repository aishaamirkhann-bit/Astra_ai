import { notFound } from "next/navigation";
import Link from "next/link";
import { Star, ShieldCheck, Wallet2, Tags, CheckCircle2, ShoppingCart, ChevronLeft } from "lucide-react";
import PageShell from "@/components/PageShell";
import { PRODUCTS } from "@/lib/mockData";

export function generateStaticParams() {
  return PRODUCTS.map((p) => ({ slug: p.slug }));
}

export default function ProductDetailPage({ params }: { params: { slug: string } }) {
  const product = PRODUCTS.find((p) => p.slug === params.slug);
  if (!product) return notFound();

  return (
    <PageShell active="Explore" title={product.name} subtitle={`Sold by ${product.seller}`}>
      <Link
        href="/explore"
        className="flex items-center gap-1 text-[11px] font-medium text-ink-500 hover:text-ink-100"
      >
        <ChevronLeft className="h-3.5 w-3.5" /> Back to Explore
      </Link>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[420px_1fr]">
        <div
          className="photo-frame aspect-square rounded-xl2"
          style={{ backgroundImage: `url(${product.image})` }}
        />

        <div className="flex flex-col gap-5">
          <div className="glass rounded-xl2 p-5">
            {product.tag && (
              <span className="mb-2 inline-block rounded-full bg-astra-gradient px-2.5 py-0.5 text-[10px] font-semibold text-white">
                {product.tag}
              </span>
            )}
            <h2 className="font-display text-xl font-semibold text-ink-100">{product.name}</h2>
            <div className="mt-1 flex items-center gap-3 text-xs text-ink-500">
              <span className="flex items-center gap-1">
                <Star className="h-3.5 w-3.5 fill-signal-hold text-signal-hold" />
                {product.rating}
              </span>
              <span className="flex items-center gap-1 text-signal-good">
                <ShieldCheck className="h-3.5 w-3.5" />
                {product.trust}% trust
              </span>
              <span>{product.category}</span>
            </div>
            <p className="mt-3 font-display text-2xl font-bold text-ink-100">{product.price}</p>
            <p className="mt-3 text-sm leading-relaxed text-ink-300">{product.description}</p>

            <div className="mt-5 flex flex-wrap gap-3">
              <button className="flex items-center gap-1.5 rounded-lg bg-astra-gradient px-5 py-2.5 text-sm font-semibold text-white shadow-glow hover:opacity-90">
                <ShoppingCart className="h-4 w-4" /> Add to Cart
              </button>
              <Link
                href="/astra-check"
                className="flex items-center gap-1.5 rounded-lg border border-base-600 px-5 py-2.5 text-sm font-medium text-ink-300 hover:border-astra-indigo/50 hover:text-ink-100"
              >
                See Full ASTRA Check
              </Link>
            </div>
          </div>

          <div className="glass rounded-xl2 p-5">
            <h3 className="mb-3 font-display text-sm font-semibold text-ink-100">ASTRA Check</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[
                { icon: Wallet2, label: "Financial Fit", detail: product.fit },
                { icon: ShieldCheck, label: "Seller Trust", detail: `${product.trust}% verified` },
                { icon: Tags, label: "Price Fairness", detail: "Below market avg." },
              ].map(({ icon: Icon, label, detail }) => (
                <div key={label} className="rounded-lg border border-base-600 bg-base-800/40 p-3">
                  <Icon className="h-4 w-4 text-astra-cyan" />
                  <p className="mt-2 text-xs font-medium text-ink-100">{label}</p>
                  <p className="mt-0.5 text-[11px] text-ink-500">{detail}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-signal-good/25 bg-signal-good/5 p-3">
              <CheckCircle2 className="h-4 w-4 text-signal-good" />
              <p className="text-xs font-semibold text-signal-good">GOOD TO BUY</p>
            </div>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
