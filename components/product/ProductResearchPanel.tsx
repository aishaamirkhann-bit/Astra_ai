"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ExternalLink, RefreshCw, Sparkles } from "lucide-react";
import { getProductResearch } from "@/lib/api";
import type { ProductResearch } from "@/lib/types";

function Sources({ report, section }: { report: ProductResearch; section: string }) {
  const urls = report.evidence[section] ?? [];
  const sources = report.sources.filter((source) => urls.includes(source.url));
  return (
    <div className="mt-4 border-t border-base-700 pt-3">
      <p className="text-[9px] font-bold uppercase tracking-wider text-ink-500">Sources</p>
      {sources.length ? (
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
          {sources.map((source) => (
            <li key={source.url}>
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[10px] text-astra-cyan hover:underline"
              >
                {source.title || source.url}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-[10px] text-ink-600">No cited web sources for this section.</p>
      )}
    </div>
  );
}

function ResearchSection({
  title,
  section,
  report,
  children,
}: {
  title: string;
  section: string;
  report: ProductResearch;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-base-700 bg-base-900/60 p-4">
      <h3 className="font-display text-sm font-bold text-ink-100">{title}</h3>
      <div className="mt-3 text-xs leading-relaxed text-ink-300">{children}</div>
      <Sources report={report} section={section} />
    </section>
  );
}

function ResearchList({ items, empty = "Not found in sourced research." }: { items: string[]; empty?: string }) {
  if (!items.length) return <p className="text-ink-600">{empty}</p>;
  return <ul className="list-disc space-y-1 pl-4">{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>;
}

export default function ProductResearchPanel({ productId }: { productId: string }) {
  const [report, setReport] = useState<ProductResearch | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadResearch = useCallback(async (refresh = false) => {
    setLoading(true);
    setError("");
    try {
      setReport(await getProductResearch(productId, refresh));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Product research could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    void loadResearch();
  }, [loadResearch]);

  return (
    <section className="glass mt-6 rounded-xl2 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-astra-cyan" />
            <h2 className="font-display text-base font-bold text-ink-100">AI Product Deep Research</h2>
          </div>
          <p className="mt-1 text-[11px] text-ink-500">Product facts and seller signals, checked against cited public sources.</p>
        </div>
        <button
          type="button"
          onClick={() => void loadResearch(true)}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-base-600 px-3 py-2 text-[11px] font-semibold text-ink-300 transition hover:border-astra-cyan/50 hover:text-white disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh research
        </button>
      </div>

      {loading && (
        <div role="status" className="mt-5 space-y-3">
          <p className="text-xs text-astra-cyan">Researching across the web…</p>
          <div className="h-4 animate-pulse rounded bg-base-800" />
          <div className="h-4 w-4/5 animate-pulse rounded bg-base-800" />
          <div className="h-24 animate-pulse rounded-xl bg-base-800" />
        </div>
      )}

      {!loading && error && (
        <div role="alert" className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/5 p-4">
          <p className="text-xs text-rose-300">{error}</p>
          <button type="button" onClick={() => void loadResearch()} className="mt-2 text-[11px] font-semibold text-rose-200 underline">
            Try again
          </button>
        </div>
      )}

      {!loading && report && (
        <div className="mt-5 space-y-4">
          {report.message && (
            <p className={`rounded-lg p-3 text-[11px] ${report.status === "partial" ? "bg-amber-400/10 text-amber-200" : "bg-base-800 text-ink-400"}`}>
              {report.message}
            </p>
          )}
          <div className="flex flex-wrap gap-2 text-[10px]">
            <span className="rounded-full bg-base-800 px-2.5 py-1 text-ink-300">Confidence: {report.confidence}</span>
            <span className={`rounded-full px-2.5 py-1 ${report.status === "complete" ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-200"}`}>
              {report.status === "complete" ? "Research complete" : "Partial research"}
            </span>
            <span className="self-center text-ink-600">Updated {new Date(report.generated_at).toLocaleString()}</span>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <ResearchSection title="Overview" section="overview" report={report}>
              {report.overview ?? <span className="text-ink-600">Not found in sourced research.</span>}
            </ResearchSection>
            <ResearchSection title="Specifications" section="specifications" report={report}>
              {Object.keys(report.specifications).length ? (
                <dl className="grid grid-cols-[minmax(0,1fr)_2fr] gap-x-4 gap-y-2">
                  {Object.entries(report.specifications).map(([key, value]) => <div className="contents" key={key}><dt className="text-ink-500">{key}</dt><dd>{value}</dd></div>)}
                </dl>
              ) : <p className="text-ink-600">Not found in sourced research.</p>}
            </ResearchSection>
            <ResearchSection title="Reviews & common complaints" section="review_summary" report={report}>
              <p><span className="text-ink-500">Overall sentiment: </span>{report.review_summary.overall_sentiment ?? "Not found"}</p>
              <div className="mt-3"><p className="mb-1 text-ink-500">Common complaints</p><ResearchList items={report.review_summary.common_complaints} /></div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div><p className="mb-1 font-semibold text-emerald-300">Pros</p><ResearchList items={report.pros} /><Sources report={report} section="pros" /></div>
                <div><p className="mb-1 font-semibold text-rose-300">Cons</p><ResearchList items={report.cons} /><Sources report={report} section="cons" /></div>
              </div>
            </ResearchSection>
            <ResearchSection title="Price comparison" section="price_comparison" report={report}>
              {report.price_comparison.length ? (
                <ul className="space-y-3">{report.price_comparison.map((item, index) => (
                  <li className="flex flex-wrap justify-between gap-2" key={`${item.url}-${index}`}>
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-astra-cyan hover:underline">{item.store}</a>
                    <span>{item.price == null ? "Price not found" : `${item.currency ?? ""} ${item.price.toLocaleString()}`}</span>
                  </li>
                ))}</ul>
              ) : <p className="text-ink-600">Not found in sourced research.</p>}
            </ResearchSection>
            <ResearchSection title="Alternatives" section="alternatives" report={report}>
              {report.alternatives.length ? <ul className="space-y-3">{report.alternatives.map((item) => (
                <li key={item.name}><p className="font-semibold text-ink-200">{item.name}</p><p>{item.why ?? "No comparison details found."}</p><p className="text-ink-500">Approx. price: {item.approx_price ?? "Not found"}</p></li>
              ))}</ul> : <p className="text-ink-600">Not found in sourced research.</p>}
            </ResearchSection>
            <ResearchSection title="Warranty & after-sales support" section="warranty_support" report={report}>
              {report.warranty_support ?? <span className="text-ink-600">Not found in sourced research.</span>}
            </ResearchSection>
            <ResearchSection title="Red flags & buying advice" section="red_flags" report={report}>
              <ResearchList items={report.red_flags} />
              <p className="mt-3">{report.buying_advice ?? "No sourced buying advice found."}</p>
              {report.evidence.buying_advice?.length ? <Sources report={report} section="buying_advice" /> : null}
            </ResearchSection>
            <ResearchSection title="Seller report" section="seller_report" report={report}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-ink-100">{report.seller_report.name ?? "Seller not listed"}</span>
                <span className={`rounded-full px-2 py-1 text-[9px] font-bold uppercase ${
                  report.seller_report.verdict === "trustworthy" ? "bg-emerald-400/10 text-emerald-300" :
                    report.seller_report.verdict === "caution" ? "bg-amber-400/10 text-amber-200" : "bg-base-700 text-ink-400"
                }`}>{report.seller_report.verdict}</span>
                {report.seller_report.rating != null && <span>Online rating: {report.seller_report.rating}</span>}
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div><p className="mb-1 text-ink-500">Reputation signals</p><ResearchList items={report.seller_report.reputation_signals} /></div>
                <div><p className="mb-1 text-ink-500">Complaints or scam reports</p><ResearchList items={report.seller_report.complaints_or_scam_reports} /></div>
              </div>
              <p className="mt-3"><span className="text-ink-500">Return policy: </span>{report.seller_report.return_policy ?? "Not found in sourced research."}</p>
            </ResearchSection>
          </div>
          <p className="text-[10px] text-ink-600">Public-web research is informational and may be incomplete; review the linked sources before making a decision.</p>
        </div>
      )}
    </section>
  );
}
