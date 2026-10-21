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
  Bell,
  Store,
  Boxes,
  ClipboardList,
  Truck,
} from "lucide-react";

export const BUYER_NAV_ITEMS = [
  { label: "Home", href: "/", icon: Home },
  { label: "Explore", href: "/explore", icon: Compass },
  { label: "Wholesale Bids", href: "/b2b", icon: Store },
  { label: "Categories", href: "/categories", icon: LayoutGrid },
  { label: "Deals", href: "/deals", icon: Tag },
  { label: "ASTRA Check", href: "/astra-check", icon: ShieldCheck },
  { label: "My Goals", href: "/goals", icon: Target },
  { label: "Wallet", href: "/wallet", icon: Wallet },
  { label: "Orders", href: "/orders", icon: Package },
  { label: "Notifications", href: "/notifications", icon: Bell },
  { label: "Messages", href: "/messages", icon: MessageSquare },
] as const;

export const SELLER_NAV_ITEMS = [
  { label: "Dashboard", href: "/seller/dashboard", icon: Home },
  { label: "My Inventory", href: "/seller/inventory", icon: Boxes },
  { label: "B2B Supplier Desk", href: "/seller/b2b", icon: Store },
  { label: "Vendor Plans", href: "/pricing", icon: Tag },
  { label: "Products", href: "/seller/products", icon: Package },
  { label: "Orders", href: "/seller/orders", icon: ClipboardList },
  { label: "ASTRA Check", href: "/seller/astra-check", icon: ShieldCheck },
  { label: "Sales Goals", href: "/seller/sales-goals", icon: Target },
  { label: "Wallet", href: "/seller/wallet", icon: Wallet },
  { label: "Fulfillment", href: "/seller/fulfillment", icon: Truck },
  { label: "Notifications", href: "/seller/notifications", icon: Bell },
  { label: "Messages", href: "/seller/messages", icon: MessageSquare },
] as const;

export const NAV_ITEMS = BUYER_NAV_ITEMS;
