/**
 * Browser microphone permission.
 *
 * Chrome/Edge persist Allow for this HTTPS origin after the first grant.
 * We do not store a flag ourselves — the Permissions-Policy must allow
 * microphone=(self) or getUserMedia fails without a prompt.
 */

export const MIC_PERMISSION_DENIED =
  "Microphone is blocked. Click Allow when your browser asks, or use the lock icon in the address bar → Site settings → Microphone → Allow.";

export type MicPermissionResult =
  | { ok: true; stream: MediaStream }
  | { ok: false; message: string };

export async function requestMicrophoneStream(
  media: Pick<MediaDevices, "getUserMedia"> | undefined = typeof navigator !== "undefined"
    ? navigator.mediaDevices
    : undefined,
): Promise<MicPermissionResult> {
  if (!media?.getUserMedia) {
    return {
      ok: false,
      message: "This browser cannot access the microphone.",
    };
  }
  try {
    const stream = await media.getUserMedia({ audio: true });
    return { ok: true, stream };
  } catch (err) {
    const name = err instanceof DOMException ? err.name : "";
    if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      return {
        ok: false,
        message: "No microphone found. Plug one in and try again.",
      };
    }
    return { ok: false, message: MIC_PERMISSION_DENIED };
  }
}

/** Release tracks after a successful prompt so Web Speech can capture on its own. */
export function releaseMediaStream(stream: MediaStream): void {
  stream.getTracks().forEach((track) => track.stop());
}
