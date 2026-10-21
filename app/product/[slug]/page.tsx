import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import PageShell from "@/components/PageShell";
import ProductDetailClient from "@/components/product/ProductDetailClient";
import { getProduct } from "@/lib/api";

export default async function ProductDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const [{ slug }, cookieStore] = await Promise.all([params, cookies()]);
  const cookieHeader = cookieStore.getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
  const product = await getProduct(slug, cookieHeader).catch(() => null);
  if (!product) notFound();
  return <PageShell active="Explore" title={product.name} subtitle={`Sold by ${product.seller}`}><ProductDetailClient initialProduct={product} /></PageShell>;
}
