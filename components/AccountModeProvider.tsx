"use client";

import { createContext, useCallback, useEffect, useMemo, useState } from "react";
import { ACCOUNT_MODE_EVENT, getAccountMode, type AccountMode } from "@/lib/auth";

type AccountModeContextValue = {
  activeMode: AccountMode;
  setActiveMode: (mode: AccountMode) => void;
};

export const AccountModeContext = createContext<AccountModeContextValue | null>(null);

export default function AccountModeProvider({ children }: { children: React.ReactNode }) {
  const [activeMode, setMode] = useState<AccountMode>("buyer");

  useEffect(() => {
    const sync = () => setMode(getAccountMode());
    sync();
    window.addEventListener(ACCOUNT_MODE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(ACCOUNT_MODE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const setActiveMode = useCallback((mode: AccountMode) => setMode(mode), []);
  const value = useMemo(() => ({ activeMode, setActiveMode }), [activeMode, setActiveMode]);

  return <AccountModeContext.Provider value={value}>{children}</AccountModeContext.Provider>;
}
