import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import GlobalVoiceFab from "@/components/GlobalVoiceFab";
import SelfHealingLog from "@/components/SelfHealingLog";
import Toaster from "@/components/Toaster";
import AccountModeProvider from "@/components/AccountModeProvider";
import SellerModeRouteSync from "@/components/SellerModeRouteSync";

export const metadata: Metadata = {
  title: "ASTRA AI — Shop Smarter. Spend Safer.",
  description: "The Trust & Financial-Consent Layer for Agentic Commerce.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-base-950 bg-astra-glow font-body antialiased">
        <ThemeProvider>
          <AccountModeProvider>
            <SellerModeRouteSync />
            {children}
            <GlobalVoiceFab />
            <Toaster />
          </AccountModeProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
