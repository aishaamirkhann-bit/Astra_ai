"use client";

import { useEffect, useState } from "react";
import Image from "next/image";

const IMAGE_BY_KIND: Array<[RegExp, string]> = [
  [/speaker|soundbar|subwoofer/, "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85"],
  [/headphone|headset/, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85"],
  [/earbud|airpod/, "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?auto=format&fit=crop&w=900&q=85"],
  [/smartwatch|wearable|\bwatch\b/, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85"],
  [/tablet|ipad/, "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=900&q=85"],
  [/monitor|display|screen/, "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=85"],
  [/keyboard/, "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=85"],
  [/laptop|computer|notebook/, "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85"],
  [/mobile|phone|smartphone/, "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85"],
  [/earring|jewelry|jewellery|necklace|bracelet|ring|jhumka/, "https://images.unsplash.com/photo-1617038220319-276d3cfab638?auto=format&fit=crop&w=900&q=85"],
  [/kurta|shalwar|kameez|lawn|suit|shirt|dress|jacket|fashion|clothing/, "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85"],
  [/sofa|couch/, "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85"],
  [/chair|stool/, "https://images.unsplash.com/photo-1505797149-43b006a668e0?auto=format&fit=crop&w=900&q=85"],
  [/table|desk/, "https://images.unsplash.com/photo-1499933374294-4584851497cc?auto=format&fit=crop&w=900&q=85"],
  [/rug|carpet/, "https://images.unsplash.com/photo-1600166898405-da9535204843?auto=format&fit=crop&w=900&q=85"],
  [/lamp|lighting/, "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85"],
  [/bag|wallet|belt|scarf|accessor/, "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85"],
  [/makeup|beauty|cosmetic|lipstick|skincare/, "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=900&q=85"],
  [/appliance|air fryer|kitchen|vacuum/, "https://images.unsplash.com/photo-1585515320310-259814833e62?auto=format&fit=crop&w=900&q=85"],
  [/audio|wearable/, "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85"],
  [/electronics & computing|laptops & computers|electronics/, "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85"],
  [/home decor|home & living/, "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=900&q=85"],
  [/furniture/, "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85"],
  [/accessories/, "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85"],
  [/mobiles/, "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85"],
];

const LOCAL_ASSET_KIND: Array<[RegExp, RegExp]> = [
  [/speaker/, /speaker|soundbar/], [/headphone/, /headphone|headset/], [/earbud/, /earbud|airpod/],
  [/watch/, /watch|wearable/], [/earring/, /earring|jewelry|jewellery|necklace|bracelet|ring|jhumka/],
  [/phone/, /mobile|phone|smartphone/], [/laptop/, /laptop|computer|notebook/],
  [/lawn/, /kurta|shalwar|kameez|lawn|suit|shirt|dress|jacket|fashion|clothing/],
  [/lipstick/, /makeup|beauty|cosmetic|lipstick|skincare/], [/air-fryer/, /appliance|air fryer|kitchen|vacuum/],
];

function kindImage(category: string, title: string): string {
  const text = `${title} ${category}`.toLowerCase();
  if (/indigo|navy|midnight blue/.test(text)) return "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=900&q=85";
  if (/ivory|cream|off.white/.test(text)) return "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=85";
  if (/sapphire|royal blue/.test(text)) return "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=900&q=85";
  return IMAGE_BY_KIND.find(([pattern]) => pattern.test(text))?.[1]
    ?? "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=900&q=85";
}

function variantImage(title: string): string | null {
  const text = title.toLowerCase();
  if (/\bindigo\b|\bnavy\b|midnight blue/.test(text)) return "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=900&q=85";
  if (/\bivory\b|\bcream\b|off.white/.test(text)) return "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=85";
  if (/\bsapphire\b|royal blue/.test(text)) return "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=900&q=85";
  return null;
}

function isMismatchedLocalAsset(src: string, category: string, title: string): boolean {
  if (!src.startsWith("/images/products/")) return false;
  const filename = src.split("/").pop()?.toLowerCase() ?? "";
  if (/default-product|fallback-tech/.test(filename)) return true;
  const expectedText = `${title} ${category}`.toLowerCase();
  const assetRule = LOCAL_ASSET_KIND.find(([assetPattern]) => assetPattern.test(filename));
  return assetRule ? !assetRule[1].test(expectedText) : true;
}

export default function CatalogProductImage({
  src,
  title,
  category,
  className = "",
  alt,
}: {
  src?: string | null;
  title: string;
  category: string;
  className?: string;
  alt?: string;
}) {
  const fallback = kindImage(category, title);
  const isGenericFallback = Boolean(src && /photo-1490481651871-ab68de25d43d|default-product|fallback-tech/.test(src));
  const initial = variantImage(title) ?? (src && !isMismatchedLocalAsset(src, category, title) && !isGenericFallback ? src : fallback);
  const [imageSrc, setImageSrc] = useState(initial);
  const [failed, setFailed] = useState(false);
  useEffect(() => { setImageSrc(initial); setFailed(false); }, [initial]);

  if (failed) {
    return (
      <div role="img" aria-label={alt ?? title} className={`grid place-items-center bg-gradient-to-br from-base-800 to-base-950 p-4 text-center ${className}`}>
        <span className="text-xs font-medium text-ink-300">{title}</span>
      </div>
    );
  }

  return (
    <Image
      unoptimized
      src={imageSrc}
      alt={alt ?? title}
      width={600}
      height={600}
      onError={() => {
        if (imageSrc !== fallback) setImageSrc(fallback);
        else setFailed(true);
      }}
      className={className}
    />
  );
}
