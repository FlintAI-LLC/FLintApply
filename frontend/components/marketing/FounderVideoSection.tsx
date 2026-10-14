"use client";

import { ProductIntroVideosGrid } from "@/components/marketing/ProductIntroVideosGrid";

/**
 * Evergreen embedded players (hook + founder). Never autoplay.
 */
export function FounderVideoSection() {
  return (
    <section className="px-6 pb-16" aria-label="Product and founder videos">
      <ProductIntroVideosGrid />
    </section>
  );
}
