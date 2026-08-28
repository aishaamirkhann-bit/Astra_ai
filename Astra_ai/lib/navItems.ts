import {
  Home,
  Compass,
  LayoutGrid,
  Tag,
  ShieldCheck,
  Target,
  Wallet,
  Package,
  MessageSquare,
} from "lucide-react";

export const NAV_ITEMS = [
  { label: "Home", href: "/", icon: Home },
  { label: "Explore", href: "/explore", icon: Compass },
  { label: "Categories", href: "/categories", icon: LayoutGrid },
  { label: "Deals", href: "/deals", icon: Tag },
  { label: "ASTRA Check", href: "/astra-check", icon: ShieldCheck },
  { label: "My Goals", href: "/goals", icon: Target },
  { label: "Wallet", href: "/wallet", icon: Wallet },
  { label: "Orders", href: "/orders", icon: Package },
  { label: "Messages", href: "/messages", icon: MessageSquare },
] as const;
