"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAccountMode } from "@/lib/useAccountMode";

export default function SellerModeRouteSync() {
  const mode = useAccountMode();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const authenticationRoute = ["/login", "/signup", "/verify-otp", "/auth/callback"].includes(pathname ?? "");
    if (mode === "seller" && pathname && !pathname.startsWith("/seller") && !authenticationRoute) {
      router.replace("/seller/dashboard");
    }
  }, [mode, pathname, router]);

  return null;
}
