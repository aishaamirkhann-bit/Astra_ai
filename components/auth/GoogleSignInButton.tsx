"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";
import { googleLogin } from "@/lib/api";
import type { UserRole } from "@/lib/types";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
            error_callback: (error: { type?: string }) => void;
          }) => void;
          renderButton: (container: HTMLElement, options: Record<string, string>) => void;
        };
      };
    };
  }
}

type GoogleSignInButtonProps = {
  role: UserRole;
};

export default function GoogleSignInButton({ role }: GoogleSignInButtonProps) {
  const buttonContainer = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

  useEffect(() => {
    if (!scriptReady || !clientId || !buttonContainer.current || !window.google) return;

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: (response) => {
        if (!response.credential) {
          setLoading(false);
          setError("Google did not return a sign-in credential. Please try again.");
          return;
        }
        setLoading(true);
        setError("");
        void googleLogin({ id_token: response.credential, role })
          .then(() => window.location.assign("/auth/callback"))
          .catch((cause: unknown) => {
            setLoading(false);
            setError(cause instanceof Error ? cause.message : "Google sign-in failed. Please try again.");
          });
      },
      error_callback: (cause) => {
        setLoading(false);
        setError(cause.type === "popup_closed" ? "Google sign-in was cancelled." : "Google sign-in could not be opened. Please try again.");
      },
    });
    window.google.accounts.id.renderButton(buttonContainer.current, {
      theme: "outline",
      size: "large",
      text: "continue_with",
      shape: "rectangular",
      width: "360",
    });
  }, [clientId, role, scriptReady]);

  return (
    <div className="flex flex-col items-center gap-2">
      {clientId ? (
        <>
          <Script
            src="https://accounts.google.com/gsi/client"
            strategy="afterInteractive"
            onLoad={() => setScriptReady(true)}
            onError={() => setError("Google sign-in could not load. Check your connection and try again.")}
          />
          <div ref={buttonContainer} aria-busy={loading} />
          {loading && <p className="text-xs text-ink-500">Signing in with Google…</p>}
        </>
      ) : (
        <p className="text-xs text-ink-500">Google sign-in is not configured.</p>
      )}
      {error && <p role="alert" className="text-center text-xs font-medium text-signal-reject">{error}</p>}
    </div>
  );
}