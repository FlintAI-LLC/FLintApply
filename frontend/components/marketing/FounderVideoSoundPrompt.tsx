"use client";

interface Props {
  open: boolean;
  onPlayWithSound: () => void;
  onPlayMuted: () => void;
}

/** Shown when the browser blocks autoplay with sound (common on mobile Safari). */
export function FounderVideoSoundPrompt({
  open,
  onPlayWithSound,
  onPlayMuted,
}: Props) {
  if (!open) return null;

  return (
    <div
      className="absolute inset-0 z-30 flex items-center justify-center rounded-lg bg-black/75 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="founder-sound-prompt-title"
    >
      <div
        className="max-w-sm rounded-xl border border-amber-400/50 bg-slate-950 px-6 py-5 text-center shadow-xl"
      >
        <p
          id="founder-sound-prompt-title"
          className="text-base font-semibold text-amber-50"
        >
          Turn on sound?
        </p>
        <p className="mt-2 text-sm leading-relaxed text-amber-100/85">
          This is a short message from Al with voice. Your browser needs a tap
          before it can play audio.
        </p>
        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={onPlayWithSound}
            className="rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-amber-500 transition-colors"
          >
            Play with sound
          </button>
          <button
            type="button"
            onClick={onPlayMuted}
            className="rounded-lg border border-amber-200/25 bg-transparent px-4 py-2.5 text-sm font-medium text-amber-100/90 hover:bg-amber-500/10 transition-colors"
          >
            Watch without sound
          </button>
        </div>
      </div>
    </div>
  );
}
