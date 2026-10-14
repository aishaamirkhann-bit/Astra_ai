"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCurrentUser } from "@/lib/api";
import { storeUserProfile } from "@/lib/auth";
import { showToast } from "@/lib/toast";

export default function SellerRouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setAuthorized(false);
    void getCurrentUser().then((user) => {
      if (cancelled) return;
      storeUserProfile(user);
      if (user.role !== "seller") {
        showToast("Switch to Seller Mode to access the seller workspace.", "info");
        router.replace("/");
        return;
      }
      setAuthorized(true);
    }).catch(() => {
      if (cancelled) return;
      showToast("Your session has expired. Please sign in to continue.", "error");
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    });
    return () => { cancelled = true; };
  }, [pathname, router]);

  if (!authorized) {
    return <main className="grid min-h-[50vh] place-items-center text-sm text-ink-500">Verifying seller access…</main>;
  }
  return children;
}
