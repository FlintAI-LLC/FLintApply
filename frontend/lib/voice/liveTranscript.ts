/** Merge typed answer text with in-progress Web Speech final + interim tokens. */
export function liveVoiceTranscript(
  typedBase: string,
  finalFromMic: string,
  interimFromMic: string,
): string {
  const spoken = [finalFromMic.trim(), interimFromMic.trim()].filter(Boolean).join(" ");
  const base = typedBase.trim();
  if (!spoken) return typedBase;
  if (!base) return spoken;
  return `${base} ${spoken}`;
}
