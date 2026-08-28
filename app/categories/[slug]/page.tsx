import { notFound } from "next/navigation";
import PageShell from "@/components/PageShell";
import CategoryProductsClient from "@/components/categories/CategoryProductsClient";

const CATEGORIES = [
  { slug: "mobiles", name: "Mobiles" },
  { slug: "laptops-computers", name: "Laptops & Computers" },
  { slug: "audio-wearables", name: "Audio & Wearables" },
  { slug: "jewelry", name: "Jewelry" },
  { slug: "clothing-fashion", name: "Clothing & Fashion" },
  { slug: "makeup-beauty", name: "Makeup & Beauty" },
  { slug: "home-appliances", name: "Home Appliances" },
  { slug: "households", name: "Households" },
];

export function generateStaticParams() {
  return CATEGORIES.map((category) => ({ slug: category.slug }));
}

export default function CategoryPage({ params }: { params: { slug: string } }) {
  const category = CATEGORIES.find((item) => item.slug === params.slug);
  if (!category) return notFound();

  return (
    <PageShell active="Categories" title={category.name} subtitle={`Browse ${category.name} from the database catalog.`}>
      <CategoryProductsClient categoryName={category.name} />
    </PageShell>
  );
}