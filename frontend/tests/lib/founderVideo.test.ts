import assert from "node:assert/strict";
import { describe, it, beforeEach, afterEach } from "node:test";

const founderStore = new Map<string, string>();
const memoryStorage: Storage = {
  getItem: (key) => founderStore.get(key) ?? null,
  setItem: (key, value) => {
    founderStore.set(key, value);
  },
  removeItem: (key) => {
    founderStore.delete(key);
  },
  clear: () => founderStore.clear(),
  key: (index) => Array.from(founderStore.keys())[index] ?? null,
  get length() {
    return founderStore.size;
  },
};
(globalThis as { localStorage?: Storage }).localStorage = memoryStorage;
(globalThis as { window?: typeof globalThis }).window = globalThis;

import {
  FOUNDER_FIRST_RUN_COMPLETE_KEY,
  isFounderFirstRunComplete,
  markFounderFirstRunComplete,
} from "@/lib/marketing/founderVideo";

describe("founderVideo first-run storage", () => {
  beforeEach(() => {
    founderStore.clear();
  });

  afterEach(() => {
    founderStore.clear();
  });

  it("starts incomplete", () => {
    assert.equal(isFounderFirstRunComplete(), false);
  });

  it("marks complete in localStorage", () => {
    markFounderFirstRunComplete();
    assert.equal(
      localStorage.getItem(FOUNDER_FIRST_RUN_COMPLETE_KEY),
      "1",
    );
    assert.equal(isFounderFirstRunComplete(), true);
  });
});
