import type { ProductDetail } from "@/lib/types";

export function isARIntent(text: string): boolean {
  const query = text.toLocaleLowerCase().normalize("NFKC");
  return /\b(ar|augmented reality|3d|three d|try[- ]?on|virtual try[- ]?on)\b/.test(query)
    || /\b(isko|is ko|mujh par|mujhpe|pehna|dikhao|dikha[o]?|kholo|khol do)\b/.test(query)
    && /\b(try|wear|preview|view|show|model|mein|me|par|pe|on)\b/.test(query)
    || /\b(try this on me|show (this )?in 3d|show (this )?in ar|open ar preview)\b/.test(query);
}

export type ARModelAsset = { src: string; label: string; illustrative: true };

const MODEL_ASSETS: Record<string, ARModelAsset> = {
  // Public CC0 shirt-on-hanger sample; deliberately labeled illustrative,
  // never represented as the exact ASTRA catalog item or a fit simulation.
  "embroidered-lawn-3pc-suit": {
    src: "https://cdn.3dassets.dev/assets/35448/v1/model.glb",
    label: "Illustrative garment sample",
    illustrative: true,
  },
};

export function getARModelForProduct(product: Pick<ProductDetail, "slug">): ARModelAsset | null {
  return MODEL_ASSETS[product.slug] ?? null;
}
