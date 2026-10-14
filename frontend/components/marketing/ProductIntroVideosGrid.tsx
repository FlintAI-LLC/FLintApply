"use client";

import {
  FOUNDER_VIDEO_DURATION_LABEL,
  FOUNDER_VIDEO_POSTER_SRC,
  FOUNDER_VIDEO_SRC,
} from "@/lib/marketing/founderVideo";
import {
  ONBOARDING_HOOK_VIDEO_DURATION_LABEL,
  ONBOARDING_HOOK_VIDEO_POSTER_SRC,
  ONBOARDING_HOOK_VIDEO_SRC,
} from "@/lib/marketing/onboardingHookVideo";
import { MarketingVideoEmbed } from "@/components/marketing/MarketingVideoEmbed";

/** Hook + founder videos side by side (onboarding welcome, landing). */
export function ProductIntroVideosGrid() {
  return (
    <div
      className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-5xl mx-auto mb-8"
      data-testid="product-intro-videos"
    >
      <MarketingVideoEmbed
        headingId="onboarding-hook-video-heading"
        heading="See how FlintApply works"
        durationLabel={ONBOARDING_HOOK_VIDEO_DURATION_LABEL}
        src={ONBOARDING_HOOK_VIDEO_SRC}
        poster={ONBOARDING_HOOK_VIDEO_POSTER_SRC}
        description="A quick walkthrough of the product story — brick bank, titles, tailor, and your guided path."
      />
      <MarketingVideoEmbed
        headingId="founder-video-heading-embed"
        heading="A note from Al"
        durationLabel={FOUNDER_VIDEO_DURATION_LABEL}
        src={FOUNDER_VIDEO_SRC}
        poster={FOUNDER_VIDEO_POSTER_SRC}
        description="Why FlintApply exists and what to expect from the solo founder behind The Flint AI."
      />
    </div>
  );
}
