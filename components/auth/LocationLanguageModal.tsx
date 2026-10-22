"use client";

import { useEffect, useState } from "react";
import { Globe2, MapPin, X } from "lucide-react";
import { COUNTRY_OPTIONS, getCountry, LANGUAGES_BY_COUNTRY, suggestCountryFromTimezone, type CountryCode, type LanguageName } from "@/lib/region";

export default function LocationModal({
  open,
  required = false,
  selectedCountry,
  onSelect,
  selectedLanguage = "English",
  onClose,
}: {
  open: boolean;
  required?: boolean;
  selectedCountry: CountryCode | null;
  onSelect: (country: CountryCode, language?: LanguageName) => void;
  selectedLanguage?: LanguageName;
  onClose: () => void;
}) {
  const [draftCountry, setDraftCountry] = useState<CountryCode | null>(selectedCountry);
  const [draftLanguage, setDraftLanguage] = useState<LanguageName>(selectedLanguage);
  const [suggestedCountry, setSuggestedCountry] = useState<CountryCode | null>(null);
  useEffect(() => {
    if (!open) return;
    setDraftCountry(selectedCountry ?? suggestCountryFromTimezone());
    setDraftLanguage(selectedLanguage);
    setSuggestedCountry(suggestCountryFromTimezone());
  }, [open, selectedCountry, selectedLanguage]);
  if (!open) return null;
  const activeCountry = draftCountry ?? selectedCountry;
  return (
    <div className="fixed inset-0 z-[120] grid place-items-center bg-slate-950/75 p-4 backdrop-blur-sm" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="location-modal-title" className="w-full max-w-md rounded-3xl border border-base-600 bg-base-900 p-5 shadow-2xl sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-astra-violet/10 px-2.5 py-1 text-[10px] font-semibold text-astra-cyan"><Globe2 className="h-3.5 w-3.5" /> Regional experience</span>
            <h2 id="location-modal-title" className="mt-3 font-display text-xl font-bold text-ink-100">Select your country or region</h2>
            <p className="mt-1 text-xs leading-relaxed text-ink-500">We’ll tailor language options and show advisory shipping estimates for your region.</p>
          </div>
          {!required && <button type="button" onClick={onClose} aria-label="Close location selector" className="rounded-lg p-2 text-ink-500 hover:bg-base-800 hover:text-ink-100"><X className="h-4 w-4" /></button>}
        </div>
        {suggestedCountry && !selectedCountry && <p className="mt-4 rounded-xl border border-cyan-300/20 bg-cyan-300/5 px-3 py-2 text-[11px] text-cyan-100">Based on your device time zone, {getCountry(suggestedCountry).name} may be a good starting point. You can choose another region below.</p>}
        <div className="mt-5 grid gap-2">
          {COUNTRY_OPTIONS.map((country) => {
            const active = activeCountry === country.code;
            return <button key={country.code} type="button" onClick={() => { setDraftCountry(country.code); setDraftLanguage("English"); }} aria-pressed={active} className={`flex items-center gap-3 rounded-2xl border p-3 text-left transition ${active ? "border-astra-violet bg-astra-violet/10" : "border-base-600 bg-base-800/50 hover:border-base-500 hover:bg-base-800"}`}>
              <span className={`grid h-10 w-10 place-items-center rounded-xl ${active ? "bg-astra-violet text-white" : "bg-base-700 text-ink-300"}`}><MapPin className="h-4 w-4" /></span>
              <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-ink-100">{country.name}</span><span className="mt-0.5 block text-[10px] text-ink-500">{country.code} · {country.currency} · {getCountry(country.code).currencyLabel}</span></span>
              <span className="text-xs font-semibold text-ink-400">{country.code}</span>
            </button>;
          })}
        </div>
        {activeCountry && <label className="mt-4 block text-xs font-medium text-ink-300">Preferred language
          <select value={LANGUAGES_BY_COUNTRY[activeCountry].some((item) => item.name === draftLanguage) ? draftLanguage : "English"} onChange={(event) => setDraftLanguage(event.target.value as LanguageName)} className="mt-2 w-full rounded-xl border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100">
            {LANGUAGES_BY_COUNTRY[activeCountry].map((language) => <option key={language.name} value={language.name}>{language.label}</option>)}
          </select>
        </label>}
        <button type="button" disabled={!activeCountry} onClick={() => { if (!activeCountry) return; onSelect(activeCountry, draftLanguage); }} className="mt-4 w-full rounded-xl bg-astra-gradient px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">Continue</button>
        <p className="mt-4 text-[10px] text-ink-600">Shipping estimates are indicative only and do not affect checkout or delivery confirmation.</p>
      </section>
    </div>
  );
}
