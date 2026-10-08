/**
 * Short landing intro chime — plays while the logo and wordmark animate in.
 * Asset: `public/brand/intro-chime.mp3` (~6s).
 */

export const INTRO_CHIME_SRC = "/brand/intro-chime.mp3" as const;

let chimeAudio: HTMLAudioElement | null = null;
let chimeStopTimer: ReturnType<typeof setTimeout> | null = null;

export function startIntroChime(playDurationMs: number): void {
  if (typeof window === "undefined") return;

  stopIntroChime();

  const audio = new Audio(INTRO_CHIME_SRC);
  audio.volume = 0.55;
  audio.preload = "auto";
  chimeAudio = audio;

  void audio.play().catch(() => {
    // Autoplay policy — intro still runs silently.
  });

  chimeStopTimer = setTimeout(() => {
    stopIntroChime();
  }, playDurationMs);
}

export function stopIntroChime(): void {
  if (chimeStopTimer !== null) {
    clearTimeout(chimeStopTimer);
    chimeStopTimer = null;
  }
  if (chimeAudio) {
    chimeAudio.pause();
    chimeAudio.currentTime = 0;
    chimeAudio = null;
  }
}
