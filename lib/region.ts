export const COUNTRY_OPTIONS = [
  { code: "PK", name: "Pakistan", currency: "PKR", currencyLabel: "Rs." },
  { code: "CN", name: "China", currency: "CNY", currencyLabel: "\u00a5" },
  { code: "IR", name: "Iran", currency: "IRR", currencyLabel: "\uFDFC" },
  { code: "AE", name: "United Arab Emirates", currency: "AED", currencyLabel: "\u062f.\u0625" },
] as const;

export type CountryCode = (typeof COUNTRY_OPTIONS)[number]["code"];
export type LanguageOption = { name: string; label: string; locale: string };
export type LanguageName = LanguageOption["name"];
export const REGION_STORAGE_KEY = "astra:region";
export const LANGUAGE_STORAGE_KEY = "astra:language";

export const LANGUAGES_BY_COUNTRY: Record<CountryCode, LanguageOption[]> = {
  PK: [
    { name: "English", label: "English", locale: "en-US" },
    { name: "Urdu", label: "Urdu", locale: "ur-PK" },
    { name: "Roman Urdu", label: "Roman Urdu", locale: "ur-PK" },
    { name: "Punjabi", label: "Punjabi", locale: "pa-PK" },
    { name: "Pashto", label: "Pashto", locale: "ps-PK" },
    { name: "Sindhi", label: "Sindhi", locale: "sd-PK" },
    { name: "Persian (Farsi / \u0641\u0627\u0631\u0633\u06cc)", label: "Persian (\u0641\u0627\u0631\u0633\u06cc)", locale: "fa-IR" },
  ],
  CN: [
    { name: "English", label: "English", locale: "en-US" },
    { name: "Chinese (Mandarin / \u4e2d\u6587)", label: "Chinese (Mandarin / \u4e2d\u6587)", locale: "zh-CN" },
  ],
  IR: [
    { name: "English", label: "English", locale: "en-US" },
    { name: "Persian (Farsi / \u0641\u0627\u0631\u0633\u06cc)", label: "Persian (Farsi / \u0641\u0627\u0631\u0633\u06cc)", locale: "fa-IR" },
  ],
  AE: [
    { name: "English", label: "English", locale: "en-US" },
    { name: "Arabic (\u0627\u0644\u0639\u0631\u0628\u064a\u0629)", label: "Arabic (\u0627\u0644\u0639\u0631\u0628\u064a\u0629)", locale: "ar-AE" },
  ],
};

export function isCountryCode(value: string | null): value is CountryCode {
  return COUNTRY_OPTIONS.some((country) => country.code === value);
}

export function getCountry(code: CountryCode) {
  return COUNTRY_OPTIONS.find((country) => country.code === code)!;
}

/** Best-effort suggestion from the browser's timezone; it never requests GPS. */
export function suggestCountryFromTimezone(timeZone?: string): CountryCode | null {
  let zone = timeZone;
  if (!zone && typeof Intl !== "undefined") {
    try { zone = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch { return null; }
  }
  if (!zone) return null;
  const countryByZone: Record<string, CountryCode> = {
    "Asia/Karachi": "PK",
    "Asia/Shanghai": "CN", "Asia/Chongqing": "CN", "Asia/Urumqi": "CN",
    "Asia/Tehran": "IR",
    "Asia/Dubai": "AE",
  };
  return countryByZone[zone] ?? null;
}

export function getSavedCountry(): CountryCode | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(REGION_STORAGE_KEY);
  return isCountryCode(value) ? value : null;
}

export function getSavedLocale(): string {
  if (typeof window === "undefined") return "en";
  const country = getSavedCountry() ?? "PK";
  const language = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  if (language === "Roman Urdu") return "roman_urdu";
  return LANGUAGES_BY_COUNTRY[country].find((option) => option.name === language)?.locale ?? "en";
}

export function saveCountry(code: CountryCode) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(REGION_STORAGE_KEY, code);
  window.dispatchEvent(new CustomEvent("astra:region-change", { detail: { country: code } }));
}

export const CURRENCY_OPTIONS = ["PKR", "CNY", "IRR", "AED", "USD"] as const;
export type DisplayCurrency = (typeof CURRENCY_OPTIONS)[number];
export const CURRENCY_STORAGE_KEY = "astra:display-currency";
export type ExchangeRates = Partial<Record<DisplayCurrency, number>>;

export function isDisplayCurrency(value: string | null): value is DisplayCurrency {
  return CURRENCY_OPTIONS.some((currency) => currency === value);
}

export function defaultDisplayCurrency(country: CountryCode): DisplayCurrency {
  return getCountry(country).currency as DisplayCurrency;
}

export function formatDisplayCurrency(amountPKR: number, currency: DisplayCurrency, rates: ExchangeRates = { PKR: 1 }): string {
  const rate = rates[currency];
  if (!Number.isFinite(amountPKR) || typeof rate !== "number" || !Number.isFinite(rate) || rate <= 0) {
    return new Intl.NumberFormat("en", { style: "currency", currency: "PKR", maximumFractionDigits: 0 }).format(amountPKR);
  }
  return new Intl.NumberFormat("en", { style: "currency", currency, maximumFractionDigits: currency === "IRR" ? 0 : 2 }).format(amountPKR * rate);
}

export function shippingEta(origin: CountryCode, destination: CountryCode): string {
  const estimates: Record<string, string> = {
    "CN-PK": "7-12 days", "IR-PK": "5-8 days", "AE-PK": "3-6 days",
    "PK-CN": "8-14 days", "PK-IR": "5-9 days", "PK-AE": "3-6 days",
    "CN-AE": "5-9 days", "IR-AE": "2-4 days", "AE-IR": "2-4 days",
    "AE-CN": "5-9 days", "CN-IR": "6-10 days", "IR-CN": "6-10 days",
  };
  return estimates[origin + "-" + destination] ?? "5-12 days";
}
