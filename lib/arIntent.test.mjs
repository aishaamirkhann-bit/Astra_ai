import assert from "node:assert/strict";
import test from "node:test";
import { getARModelForProduct, isARIntent } from "./arIntent.ts";

test("AR intents include English and Roman Urdu requests", () => {
  assert.equal(isARIntent("Try this on me"), true);
  assert.equal(isARIntent("Is ko 3D mein dikhao"), true);
  assert.equal(isARIntent("AR preview kholo"), true);
  assert.equal(isARIntent("Find a blue shirt under 5000"), false);
});

test("product without a mapped model takes the safe fallback path", () => {
  assert.equal(getARModelForProduct({ slug: "samsung-galaxy-s25-ultra" }), null);
  assert.equal(getARModelForProduct({ slug: "embroidered-lawn-3pc-suit" })?.illustrative, true);
});
