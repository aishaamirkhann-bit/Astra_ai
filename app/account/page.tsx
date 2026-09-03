"use client";

import { useEffect, useState } from "react";
import PageShell from "@/components/PageShell";
import { getCurrentUser } from "@/lib/api";
import type { LoginResponse } from "@/lib/types";

export default function AccountPage() {
  const [user, setUser] = useState<LoginResponse["user"] | null>(null);
  useEffect(() => { void getCurrentUser().then(setUser); }, []);
  return <PageShell active="" title="Account Settings" subtitle="Your authenticated Astra profile and preferences."><section className="glass max-w-xl rounded-xl2 p-6">{user ? <div className="space-y-4"><div className="grid h-14 w-14 place-items-center rounded-2xl bg-astra-gradient font-display text-xl font-bold text-white">{user.name[0].toUpperCase()}</div><div><p className="text-xs text-ink-500">Name</p><p className="text-sm font-semibold text-ink-100">{user.name}</p></div><div><p className="text-xs text-ink-500">Email</p><p className="text-sm text-ink-100">{user.email}</p></div><div><p className="text-xs text-ink-500">Role</p><p className="text-sm capitalize text-ink-100">{user.role}</p></div><div><p className="text-xs text-ink-500">Preferred language</p><p className="text-sm text-ink-100">{user.preferred_language}</p></div></div> : <p className="text-xs text-ink-500">Loading secure profile…</p>}</section></PageShell>;
}
