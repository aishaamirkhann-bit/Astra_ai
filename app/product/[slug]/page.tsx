import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import PageShell from "@/components/PageShell";
import ProductDetailClient from "@/components/product/ProductDetailClient";
import { getProduct } from "@/lib/api";

export default async function ProductDetailPage({ params }: { params: { slug: string } }) {
  const cookieHeader = cookies().getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
  const product = await getProduct(params.slug, cookieHeader).catch(() => null);
  if (!product) notFound();
  return <PageShell active="Explore" title={product.name} subtitle={`Sold by ${product.seller}`}><ProductDetailClient initialProduct={product} /></PageShell>;
}
