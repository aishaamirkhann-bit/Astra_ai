"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Barcode,
  Camera,
  CheckCircle2,
  ImagePlus,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  createSellerInventory,
  deleteSellerInventory,
  getSellerInventory,
  lookupSellerBarcode,
  updateSellerInventory,
  type BarcodeProductLookup,
  type SellerInventoryItem,
} from "@/lib/api";
import { showToast } from "@/lib/toast";

type InventoryForm = {
  title: string;
  brand: string;
  category: string;
  subcategory: string;
  color: string;
  size: string;
  variant: string;
  description: string;
  specifications: string;
  image_url: string;
  price: string;
  seller_price_floor: string;
  stock_count: string;
};

const EMPTY_FORM: InventoryForm = {
  title: "",
  brand: "",
  category: "",
  subcategory: "",
  color: "",
  size: "",
  variant: "",
  description: "",
  specifications: "",
  image_url: "",
  price: "",
  seller_price_floor: "",
  stock_count: "",
};

type BarcodeDetectorConstructor = new (options: { formats: string[] }) => {
  detect(source: HTMLVideoElement): Promise<Array<{ rawValue: string }>>;
};

type CameraWindow = Window & { BarcodeDetector?: BarcodeDetectorConstructor };

function specificationsText(specifications: Record<string, string>): string {
  return Object.entries(specifications).map(([key, value]) => `${key}: ${value}`).join("\n");
}

function parseSpecifications(value: string): Record<string, string> {
  return Object.fromEntries(
    value.split("\n")
      .map((line) => line.split(/:\s*/, 2))
      .filter(([key, item]) => Boolean(key?.trim() && item?.trim()))
      .map(([key, item]) => [key.trim(), item.trim()]),
  );
}

export default function SellerInventoryForm() {
  const [items, setItems] = useState<SellerInventoryItem[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [barcode, setBarcode] = useState("");
  const [lookupState, setLookupState] = useState<"idle" | "loading" | "found" | "not-found">("idle");
  const [matchedProduct, setMatchedProduct] = useState<BarcodeProductLookup | null>(null);
  const [form, setForm] = useState<InventoryForm>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const requestId = useRef(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  async function load() {
    setError("");
    try {
      setItems(await getSellerInventory());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load seller inventory.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const performLookup = useCallback(async (value: string) => {
    const cleanBarcode = value.trim();
    const currentRequest = ++requestId.current;
    if (!/^[0-9]{8,14}$/.test(cleanBarcode)) {
      setLookupState("idle");
      if (cleanBarcode) setError("Enter a barcode containing 8 to 14 digits.");
      return;
    }

    setError("");
    setSuccess("");
    setLookupState("loading");
    try {
      const product = await lookupSellerBarcode(cleanBarcode);
      if (currentRequest !== requestId.current) return;
      setMatchedProduct(product);
      setLookupState("found");
      setForm({
        title: product.title,
        brand: product.brand,
        category: product.category,
        subcategory: product.subcategory,
        color: product.color,
        size: product.size,
        variant: product.variant,
        description: product.description,
        specifications: specificationsText(product.specifications),
        image_url: product.image_url,
        price: String(product.market_price),
        seller_price_floor: "",
        stock_count: "",
      });
      showToast("Product Details Loaded from Barcode", "success");
    } catch (cause) {
      if (currentRequest !== requestId.current) return;
      const message = cause instanceof Error ? cause.message : "Could not look up this barcode.";
      if (message.toLowerCase().includes("new barcode detected")) {
        setMatchedProduct(null);
        setLookupState("not-found");
        setForm((current) => ({ ...EMPTY_FORM, price: current.price, stock_count: current.stock_count }));
        setSuccess("");
      } else {
        setLookupState("idle");
        setError(message);
      }
    }
  }, []);

  useEffect(() => {
    const cleanBarcode = barcode.trim();
    if (!/^[0-9]{8,14}$/.test(cleanBarcode) || matchedProduct?.barcode === cleanBarcode) return;
    const timeout = window.setTimeout(() => void performLookup(cleanBarcode), 450);
    return () => window.clearTimeout(timeout);
  }, [barcode, matchedProduct, performLookup]);

  useEffect(() => {
    if (!cameraOpen) return;
    const preview = videoRef.current;
    let stream: MediaStream | undefined;
    let frame = 0;
    let cancelled = false;

    async function startScanner() {
      const Detector = (window as CameraWindow).BarcodeDetector;
      if (!Detector) {
        setError("Barcode scanning is not supported by this browser. Type the barcode instead.");
        setCameraOpen(false);
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Camera access is not available. Type the barcode instead.");
        setCameraOpen(false);
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        const video = videoRef.current;
        if (!video) throw new Error("Camera preview could not be started.");
        video.srcObject = stream;
        await video.play();
        const detector = new Detector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"] });
        const scan = async () => {
          if (cancelled || !videoRef.current) return;
          try {
            const detections = await detector.detect(videoRef.current);
            const value = detections[0]?.rawValue;
            if (value && /^[0-9]{8,14}$/.test(value)) {
              setBarcode(value);
              setCameraOpen(false);
              return;
            }
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Could not read a barcode from the camera.");
            setCameraOpen(false);
            return;
          }
          frame = window.requestAnimationFrame(() => void scan());
        };
        frame = window.requestAnimationFrame(() => void scan());
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Camera permission was denied.");
        setCameraOpen(false);
      }
    }

    void startScanner();
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
      stream?.getTracks().forEach((track) => track.stop());
      if (preview) preview.srcObject = null;
    };
  }, [cameraOpen]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setCreating(true);
    try {
      await createSellerInventory({
        title: form.title,
        category: form.category,
        description: form.description,
        image_url: form.image_url || "/images/products/fallback-tech.jpg",
        price: Number(form.price),
        ...(form.seller_price_floor ? { seller_price_floor: Number(form.seller_price_floor) } : {}),
        stock_count: Number(form.stock_count),
        ...(barcode.trim() ? { barcode: barcode.trim() } : {}),
        brand: form.brand,
        subcategory: form.subcategory,
        color: form.color,
        size: form.size,
        variant: form.variant,
        specifications: parseSpecifications(form.specifications),
        quality_tags: matchedProduct?.quality_tags ?? [],
      });
      setForm(EMPTY_FORM);
      setBarcode("");
      setMatchedProduct(null);
      setLookupState("idle");
      setSuccess("Product listing added to your inventory.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the product listing.");
    } finally {
      setCreating(false);
    }
  }

  async function edit(item: SellerInventoryItem, field: "price" | "seller_price_floor" | "stock_count", value: number) {
    setError("");
    try {
      await updateSellerInventory(item.id, { [field]: value });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update this listing.");
    }
  }

  async function remove(id: string) {
    setError("");
    try {
      await deleteSellerInventory(id);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete this listing.");
    }
  }

  const verified = matchedProduct?.verified === true;
  const field = (key: keyof InventoryForm, label: string, required = false) => (
    <label key={key} className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300">
      {label}
      <input
        aria-label={label}
        required={required}
        maxLength={key === "title" ? 160 : 120}
        value={form[key]}
        disabled={verified}
        onChange={(event) => setForm({ ...form, [key]: event.target.value })}
        placeholder={label}
        className="rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-astra-violet/50 focus:outline-none disabled:cursor-not-allowed disabled:opacity-75"
      />
    </label>
  );

  return (
    <section className="glass rounded-xl2 p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-display text-base font-bold text-ink-100">Inventory Management</h2>
          <p className="mt-1 text-xs text-ink-500">Scan or type a barcode to prefill a product listing.</p>
        </div>
        <div className="inline-flex items-center gap-2 self-start rounded-lg border border-astra-violet/20 bg-astra-gradient-soft px-3 py-2 text-[11px] text-ink-300">
          <Barcode className="h-4 w-4 text-astra-cyan" />
          Barcode quick add
        </div>
      </div>

      <form onSubmit={create} className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300">
            Barcode / EAN / UPC
            <div className="flex gap-2">
              <input
                aria-label="Barcode / EAN / UPC"
                inputMode="numeric"
                value={barcode}
                onChange={(event) => {
                  requestId.current += 1;
                  setBarcode(event.target.value.replace(/\D/g, "").slice(0, 14));
                  setMatchedProduct(null);
                  setLookupState("idle");
                  setForm(EMPTY_FORM);
                  setError("");
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void performLookup(barcode);
                  }
                }}
                placeholder="e.g. 890123456001"
                className="min-w-0 flex-1 rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-astra-violet/50 focus:outline-none"
              />
              <button
                type="button"
                aria-label="Look up barcode"
                title="Look up barcode"
                disabled={lookupState === "loading"}
                onClick={() => void performLookup(barcode)}
                className="inline-flex items-center justify-center rounded-lg border border-astra-violet/25 bg-astra-gradient-soft px-3 text-astra-cyan disabled:opacity-50"
              >
                {lookupState === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Barcode className="h-4 w-4" />}
              </button>
              <button
                type="button"
                aria-label={cameraOpen ? "Close barcode scanner" : "Open barcode scanner"}
                title={cameraOpen ? "Close scanner" : "Scan with camera"}
                onClick={() => {
                  setError("");
                  setCameraOpen((open) => !open);
                }}
                className="inline-flex items-center justify-center rounded-lg border border-base-600 bg-base-800 px-3 text-ink-300 hover:text-astra-cyan"
              >
                {cameraOpen ? <X className="h-4 w-4" /> : <Camera className="h-4 w-4" />}
              </button>
            </div>
          </label>
          {cameraOpen && (
            <video ref={videoRef} aria-label="Barcode scanner camera preview" autoPlay muted playsInline className="max-h-48 w-full rounded-lg border border-astra-violet/25 bg-base-800 object-cover" />
          )}
          {lookupState === "loading" && <span role="status" className="text-[11px] text-astra-cyan">Looking up product details…</span>}
          {lookupState === "not-found" && <span role="status" className="rounded-lg border border-signal-hold/20 bg-signal-hold/5 px-3 py-2 text-[11px] text-signal-hold">New Barcode Detected - Please enter product details manually.</span>}
        </div>
        {field("title", "Product name", true)}
        {field("brand", "Brand")}
        {field("category", "Category", true)}
        {field("subcategory", "Subcategory")}
        {field("color", "Color")}
        {field("size", "Size")}
        {field("variant", "Variant")}
        <label className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300 md:col-span-2 xl:col-span-3">
          Description
          <textarea
            aria-label="Description"
            required
            maxLength={2000}
            rows={3}
            disabled={verified}
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            placeholder="Product description"
            className="resize-y rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-astra-violet/50 focus:outline-none disabled:cursor-not-allowed disabled:opacity-75"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300 md:col-span-2">
          Product specifications <span className="font-normal text-ink-500">(one “name: value” per line; add model_url: https://…/model.glb for room AR)</span>
          <textarea
            aria-label="Product specifications"
            rows={3}
            disabled={verified}
            value={form.specifications}
            onChange={(event) => setForm({ ...form, specifications: event.target.value })}
            placeholder={"Storage: 128 GB\nCondition: New"}
            className="resize-y rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-astra-violet/50 focus:outline-none disabled:cursor-not-allowed disabled:opacity-75"
          />
        </label>
        <div className="flex flex-col gap-2 md:col-span-2">
          <label className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300">
            Product image URL
            <div className="flex items-center gap-2 rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 focus-within:border-astra-violet/50">
              <ImagePlus className="h-4 w-4 shrink-0 text-ink-500" />
              <input
                aria-label="Product image URL"
                type="text"
                disabled={verified}
                value={form.image_url}
                onChange={(event) => setForm({ ...form, image_url: event.target.value })}
                placeholder="/images/products/product.jpg"
                className="min-w-0 flex-1 bg-transparent text-xs text-ink-100 placeholder:text-ink-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-75"
              />
            </div>
          </label>
          {form.image_url && (
            <img
              src={form.image_url}
              alt={`Preview of ${form.title || "product"}`}
              className="h-28 w-36 rounded-lg border border-base-600 bg-base-800 object-contain p-2"
            />
          )}
        </div>
        {verified && matchedProduct && (
          <div className="flex flex-col gap-2 md:col-span-2 xl:col-span-3">
            <p className="text-[11px] font-medium text-ink-300">Catalog &amp; ASTRA Check tags</p>
            <div className="flex flex-wrap gap-2">
              {matchedProduct.quality_tags.map((tag) => (
                <span key={tag} className="inline-flex items-center gap-1 rounded-full border border-astra-violet/20 bg-astra-gradient-soft px-2.5 py-1 text-[10px] text-ink-300">
                  <CheckCircle2 className="h-3 w-3 text-astra-cyan" />{tag}
                </span>
              ))}
            </div>
            <p className="text-[10px] text-ink-500">Barcode catalog data is matched; the seller’s item authenticity still requires ASTRA Check.</p>
          </div>
        )}
        <label className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300">
          Selling price (PKR)
          <input
            aria-label="Price"
            required
            type="number"
            min="1"
            value={form.price}
            onChange={(event) => setForm({ ...form, price: event.target.value })}
            placeholder="Price"
            className="rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-astra-violet/50 focus:outline-none"
          />
          {verified && matchedProduct && <span className="text-[10px] text-ink-500">Suggested market reference: Rs. {matchedProduct.market_price.toLocaleString("en-PK")}</span>}
        </label>
        <label className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300">
          Minimum bundle price (PKR)
          <input
            aria-label="Minimum bundle price"
            type="number"
            min="1"
            max={form.price || undefined}
            value={form.seller_price_floor}
            onChange={(event) => setForm({ ...form, seller_price_floor: event.target.value })}
            placeholder={form.price || "Defaults to selling price"}
            className="rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-astra-violet/50 focus:outline-none"
          />
          <span className="text-[10px] text-ink-500">ASTRA will not quote a bundle below this price. Blank means the selling price.</span>
        </label>
        <label className="flex flex-col gap-1.5 text-[11px] font-medium text-ink-300">
          Stock quantity
          <input
            aria-label="Stock"
            required
            type="number"
            min="0"
            value={form.stock_count}
            onChange={(event) => setForm({ ...form, stock_count: event.target.value })}
            placeholder="Stock"
            className="rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-astra-violet/50 focus:outline-none"
          />
        </label>
        <div className="flex items-end md:col-span-2 xl:col-span-3">
          <button
            type="submit"
            disabled={creating || lookupState === "loading"}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-astra-gradient px-3 py-2.5 text-xs font-bold text-white transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-60 sm:w-auto sm:px-5"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {creating ? "Adding listing…" : "Add listing"}
          </button>
        </div>
      </form>

      {matchedProduct && (
        <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-astra-violet/25 bg-astra-gradient-soft px-3 py-2.5 text-[11px] text-ink-300">
          <Sparkles className="h-4 w-4" />
          <span>Barcode match:</span>
          <span className="font-semibold text-ink-100">{matchedProduct.title}</span>
          <CheckCircle2 className="ml-auto h-4 w-4 text-astra-cyan" />
        </div>
      )}
      {error && <p role="alert" className="mt-3 rounded-lg bg-signal-reject/10 px-3 py-2 text-xs text-signal-reject">{error}</p>}
      {success && <p role="status" className="mt-3 rounded-lg bg-signal-good/10 px-3 py-2 text-xs text-signal-good">{success}</p>}

      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-ink-500">
            <tr>
              <th className="p-2">Product</th>
              <th>Bundle floor</th>
              <th>Price</th>
              <th>Stock</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t border-base-600">
                <td className="p-2 font-semibold text-ink-100">
                  {item.title}
                  <span className="block text-[10px] text-ink-500">{item.category}</span>
                  {item.barcode && <span className="block text-[10px] text-ink-500">Barcode: {item.barcode}</span>}
                </td>
                <td>
                  <input
                    aria-label={`Bundle floor for ${item.title}`}
                    type="number"
                    min="1"
                    max={item.price}
                    defaultValue={item.seller_price_floor}
                    onBlur={(event) => {
                      const floor = Number(event.target.value);
                      if (Number.isFinite(floor) && floor > 0 && floor <= item.price && floor !== item.seller_price_floor) void edit(item, "seller_price_floor", floor);
                      else if (floor > item.price) event.target.value = String(item.seller_price_floor);
                    }}
                    className="w-24 rounded bg-base-800 p-2 text-ink-100"
                  />
                </td>
                <td>
                  <input
                    aria-label={`Price for ${item.title}`}
                    type="number"
                    min="1"
                    defaultValue={item.price}
                    onBlur={(event) => {
                      const price = Number(event.target.value);
                      if (Number.isFinite(price) && price > 0 && price !== item.price) void edit(item, "price", price);
                    }}
                    className="w-24 rounded bg-base-800 p-2 text-ink-100"
                  />
                </td>
                <td>
                  <input
                    aria-label={`Stock for ${item.title}`}
                    type="number"
                    min="0"
                    defaultValue={item.stock_count}
                    onBlur={(event) => {
                      const stock = Number(event.target.value);
                      if (Number.isInteger(stock) && stock >= 0 && stock !== item.stock_count) void edit(item, "stock_count", stock);
                    }}
                    className="w-20 rounded bg-base-800 p-2 text-ink-100"
                  />
                </td>
                <td className={item.stock_count ? "text-emerald-400" : "text-rose-400"}>{item.status.replaceAll("_", " ")}</td>
                <td>
                  <button type="button" title="Save changes when leaving a field" className="mr-2 text-astra-cyan">
                    <Save className="h-4 w-4" />
                  </button>
                  <button type="button" aria-label={`Delete ${item.title}`} onClick={() => void remove(item.id)} className="text-rose-400">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr><td colSpan={6} className="p-6 text-center text-ink-500">No listings yet. Add a product to start your inventory.</td></tr>
            )}
            {loading && (
              <tr><td colSpan={6} className="p-6 text-center text-ink-500">Loading inventory…</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
