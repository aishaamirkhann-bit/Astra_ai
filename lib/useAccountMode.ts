"use client";

import { useContext } from "react";
import { AccountModeContext } from "@/components/AccountModeProvider";
import type { AccountMode } from "@/lib/auth";

export function useAccountMode(): AccountMode {
  const context = useContext(AccountModeContext);
  if (!context) throw new Error("useAccountMode must be used inside AccountModeProvider");
  return context.activeMode;
}
