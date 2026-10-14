"use client";

type Props = {
  heading: string;
  description: string;
  src: string;
  poster: string;
  durationLabel: string;
  headingId: string;
};

/** Embedded marketing video card (controls, no autoplay). */
export function MarketingVideoEmbed({
  heading,
  description,
  src,
  poster,
  durationLabel,
  headingId,
}: Props) {
  return (
    <article
      className="rounded-2xl border border-amber-400/40 bg-black p-1 shadow-[0_0_32px_rgba(245,158,11,0.1)] h-full flex flex-col"
      aria-labelledby={headingId}
    >
      <div className="rounded-xl bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.12)_0%,#0a0a0a_70%)] p-2 sm:p-3 flex flex-col flex-1">
        <h3
          id={headingId}
          className="text-center text-base font-semibold text-amber-50 mb-2"
        >
          {heading} ({durationLabel})
        </h3>
        <video
          className="w-full rounded-lg bg-black aspect-video"
          src={src}
          poster={poster}
          playsInline
          controls
          preload="metadata"
        />
        <p className="mt-2 text-center text-xs text-amber-100/70 leading-relaxed">
          {description}
        </p>
      </div>
    </article>
  );
}
