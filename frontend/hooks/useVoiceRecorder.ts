"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  MIC_PERMISSION_DENIED,
  releaseMediaStream,
  requestMicrophoneStream,
} from "@/lib/voice/microphonePermission";

export type VoiceState = "idle" | "speaking" | "recording" | "transcribing" | "preview";

/**
 * Unified voice-recording hook.
 *
 * Primary path  — Web Speech API (Chrome / Edge):
 *   Free on every plan. Live interim text appears as the user speaks.
 *   Transcript is ready the moment the user stops; no backend call needed.
 *
 * Fallback path — MediaRecorder → platform Whisper endpoint:
 *   Used when SpeechRecognition is not available (Firefox, Safari).
 *   Gated by the subscriber's whisper_uses_per_period allowance; the free plan
 *   is rejected with `whisper_not_available`.
 */

function formatDuration(ms: number) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

interface UseVoiceRecorderOptions {
  /** Called with a final blob only on the MediaRecorder fallback path. */
  onBlob?: (blob: Blob) => Promise<void>;
}

export function useVoiceRecorder({ onBlob }: UseVoiceRecorderOptions = {}) {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [finalText, setFinalText]   = useState("");
  const [interimText, setInterimText] = useState("");
  const [recordingMs, setRecordingMs] = useState(0);
  const [error, setError]           = useState<string | null>(null);

  const recognitionRef  = useRef<SpeechRecognition | null>(null);
  const mediaRecRef     = useRef<MediaRecorder | null>(null);
  const chunksRef       = useRef<Blob[]>([]);
  const timerRef        = useRef<ReturnType<typeof setInterval> | null>(null);
  const startMsRef      = useRef(0);
  const accumulatedRef  = useRef("");
  const interimRef      = useRef("");
  const wantListeningRef = useRef(false);

  const supportsWebSpeech =
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition ?? window.webkitSpeechRecognition);

  // Cleanup on unmount
  useEffect(() => () => {
    recognitionRef.current?.stop();
    mediaRecRef.current?.stream?.getTracks().forEach((t) => t.stop());
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  const startTimer = () => {
    startMsRef.current = Date.now();
    setRecordingMs(0);
    timerRef.current = setInterval(
      () => setRecordingMs(Date.now() - startMsRef.current),
      500,
    );
  };

  const stopTimer = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  const flushTranscript = () => {
    const flushed = [accumulatedRef.current, interimRef.current]
      .map((s) => s.trim())
      .filter(Boolean)
      .join(" ");
    if (flushed) {
      accumulatedRef.current = flushed;
      interimRef.current = "";
      setFinalText(flushed);
      setInterimText("");
    }
    return flushed;
  };

  // ── Web Speech API path ────────────────────────────────────────────────────
  const startWebSpeech = useCallback(() => {
    const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Ctor) return false;

    const rec = new Ctor();
    rec.continuous      = true;
    rec.interimResults  = true;
    rec.lang            = "en-US";
    recognitionRef.current = rec;
    accumulatedRef.current = "";
    interimRef.current = "";
    wantListeningRef.current = true;

    rec.onresult = (e: SpeechRecognitionEvent) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const text = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          accumulatedRef.current += (accumulatedRef.current ? " " : "") + text.trim();
        } else {
          interim = text;
        }
      }
      interimRef.current = interim;
      setFinalText(accumulatedRef.current);
      setInterimText(interim);
    };

    rec.onerror = (e: SpeechRecognitionErrorEvent) => {
      if (e.error === "aborted" || e.error === "no-speech") return;
      wantListeningRef.current = false;
      setError(
        e.error === "not-allowed" || e.error === "service-not-allowed"
          ? MIC_PERMISSION_DENIED
          : `Speech recognition error: ${e.error}`,
      );
      setVoiceState("idle");
      stopTimer();
    };

    rec.onend = () => {
      // Chrome ends a recognition session after ~60s even with continuous=true.
      if (wantListeningRef.current) {
        window.setTimeout(() => {
          if (!wantListeningRef.current || recognitionRef.current !== rec) return;
          try {
            rec.start();
          } catch {
            wantListeningRef.current = false;
            stopTimer();
            flushTranscript();
            recognitionRef.current = null;
            setVoiceState((s) => (s === "speaking" ? "preview" : s));
          }
        }, 150);
        return;
      }
      stopTimer();
      flushTranscript();
      recognitionRef.current = null;
      setVoiceState((s) => (s === "speaking" ? "preview" : s));
    };

    try {
      rec.start();
    } catch (err) {
      wantListeningRef.current = false;
      recognitionRef.current = null;
      setError(err instanceof Error ? err.message : "Could not start the microphone.");
      return false;
    }
    startTimer();
    setVoiceState("speaking");
    setFinalText("");
    setInterimText("");
    setError(null);
    return true;
  }, []);

  // ── MediaRecorder fallback ─────────────────────────────────────────────────
  const startMediaRecorder = useCallback(async (stream: MediaStream): Promise<boolean> => {
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";

    chunksRef.current = [];
    const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    mr.onstop = () => stream.getTracks().forEach((t) => t.stop());
    mr.start(250);
    mediaRecRef.current = mr;
    startTimer();
    setVoiceState("recording");
    setFinalText("");
    setError(null);
    return true;
  }, []);

  // ── Start (picks the best path) ────────────────────────────────────────────
  const start = useCallback(async (): Promise<boolean> => {
    // getUserMedia is what shows Chrome's persistent permission prompt.
    // After Allow, the browser remembers it for this HTTPS origin.
    const primed = await requestMicrophoneStream();
    if (!primed.ok) {
      setError(primed.message);
      setVoiceState("idle");
      return false;
    }
    if (supportsWebSpeech) {
      releaseMediaStream(primed.stream);
      const ok = startWebSpeech();
      if (!ok) {
        setError("Could not start the microphone.");
        return false;
      }
      return true;
    }
    return startMediaRecorder(primed.stream);
  }, [supportsWebSpeech, startWebSpeech, startMediaRecorder]);

  // ── Stop ───────────────────────────────────────────────────────────────────
  const stop = useCallback(async () => {
    stopTimer();

    // Web Speech path
    if (recognitionRef.current) {
      wantListeningRef.current = false;
      flushTranscript();
      recognitionRef.current.stop();
      // onend will set voiceState → "preview"
      return;
    }
    if (wantListeningRef.current || accumulatedRef.current || interimRef.current) {
      wantListeningRef.current = false;
      flushTranscript();
      setVoiceState("preview");
      return;
    }

    // MediaRecorder fallback path
    const mr = mediaRecRef.current;
    if (!mr) {
      const flushed = flushTranscript();
      setVoiceState(flushed ? "preview" : "idle");
      return;
    }
    await new Promise<void>((resolve) => {
      mr.addEventListener("stop", () => resolve(), { once: true });
      mr.stop();
    });
    mediaRecRef.current = null;

    if (!onBlob) {
      setVoiceState("preview");
      return;
    }
    setVoiceState("transcribing");
    try {
      const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
      await onBlob(blob);
      setVoiceState("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transcription failed.");
      setVoiceState("idle");
    }
  }, [onBlob]);

  const reset = useCallback(() => {
    wantListeningRef.current = false;
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    accumulatedRef.current = "";
    interimRef.current = "";
    mediaRecRef.current?.stream?.getTracks().forEach((t) => t.stop());
    mediaRecRef.current = null;
    stopTimer();
    setVoiceState("idle");
    setFinalText("");
    setInterimText("");
    setError(null);
    setRecordingMs(0);
  }, []);

  return {
    voiceState,
    finalText,
    setFinalText,
    interimText,
    recordingMs,
    durationLabel: formatDuration(recordingMs),
    error,
    setError,
    supportsWebSpeech,
    start,
    stop,
    reset,
  };
}
