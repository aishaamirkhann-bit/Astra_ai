"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CURRENCY_STORAGE_KEY,
  defaultDisplayCurrency,
  formatDisplayCurrency,
  getSavedCountry,
  isDisplayCurrency,
  type DisplayCurrency,
  type ExchangeRates,
} from "@/lib/region";

const RATES_CACHE_KEY = "astra:display-rates-pkr";
const RATES_TTL_MS = 12 * 60 * 60 * 1000;

export function useRegionalCurrency() {
  const [currency, setCurrencyState] = useState<DisplayCurrency>("PKR");
  const [rates, setRates] = useState<ExchangeRates>({ PKR: 1 });

  useEffect(() => {
    const syncCurrency = () => {
      const country = getSavedCountry() ?? "PK";
      const saved = window.localStorage.getItem(CURRENCY_STORAGE_KEY);
      setCurrencyState(isDisplayCurrency(saved) ? saved : defaultDisplayCurrency(country));
    };
    syncCurrency();
    window.addEventListener("astra:region-change", syncCurrency);
    window.addEventListener("astra:currency-change", syncCurrency);
    window.addEventListener("storage", syncCurrency);

    try {
      const cached = JSON.parse(window.localStorage.getItem(RATES_CACHE_KEY) ?? "null") as { at?: number; rates?: ExchangeRates } | null;
      if (cached?.at && Date.now() - cached.at < RATES_TTL_MS && cached.rates?.PKR === 1) {
        setRates(cached.rates);
      }
    } catch { /* Ignore malformed display-only cache. */ }

    void fetch("https://open.er-api.com/v6/latest/PKR")
      .then((response) => response.ok ? response.json() as Promise<{ result?: string; rates?: Record<string, number> }> : Promise.reject(new Error("Rate service unavailable")))
      .then((payload) => {
        if (payload.result !== "success" || !payload.rates) return;
        const next: ExchangeRates = { PKR: 1 };
        for (const code of ["CNY", "IRR", "AED", "USD"] as const) {
          const rate = payload.rates[code];
          if (Number.isFinite(rate) && rate > 0) next[code] = rate;
        }
        setRates(next);
        window.localStorage.setItem(RATES_CACHE_KEY, JSON.stringify({ at: Date.now(), rates: next }));
      })
      .catch(() => undefined);

    return () => {
      window.removeEventListener("astra:region-change", syncCurrency);
      window.removeEventListener("astra:currency-change", syncCurrency);
      window.removeEventListener("storage", syncCurrency);
    };
  }, []);

  const setCurrency = useCallback((next: DisplayCurrency) => {
    window.localStorage.setItem(CURRENCY_STORAGE_KEY, next);
    setCurrencyState(next);
    window.dispatchEvent(new CustomEvent("astra:currency-change", { detail: { currency: next } }));
  }, []);
  const formatPrice = useCallback((amountPKR: number) => formatDisplayCurrency(amountPKR, currency, rates), [currency, rates]);

  return { currency, setCurrency, formatPrice, ratesReady: Boolean(rates[currency]) };
}
