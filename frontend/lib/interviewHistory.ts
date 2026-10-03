import type { InterviewMessage } from "@/lib/story";

export const INTERVIEW_COMPLETE_SENTINEL = "INTERVIEW_COMPLETE";

/** Align with story draft / backend interview turn cap. */
export const MAX_INTERVIEW_ANSWER_CHARS = 20_000;

export function isInterviewCompleteSentinel(text: string): boolean {
  return text.trim() === INTERVIEW_COMPLETE_SENTINEL;
}

export function isResumeLikeInterviewerLeak(text: string): boolean {
  const sample = text.trim().slice(0, 400).toUpperCase();
  if (sample.includes("PROFESSIONAL SUMMARY")) return true;
  if (sample.startsWith("SKILLS") && sample.includes("EXPERIENCE")) return true;
  if (sample.includes("EXPERIENCE\n") && sample.includes("EDUCATION")) return true;
  return false;
}

/** Drop sentinel turns, resume leaks, and empty rows before submit or persist. */
export function sanitizeInterviewHistory(
  history: InterviewMessage[],
): InterviewMessage[] {
  const out: InterviewMessage[] = [];

  for (const msg of history) {
    let text = msg.text.trim();
    if (!text) continue;

    if (msg.role === "interviewer") {
      if (isInterviewCompleteSentinel(text)) continue;
      if (/^INTERVIEW_COMPLETE\b/i.test(text)) {
        text = text.replace(/^INTERVIEW_COMPLETE\s*/i, "").trim();
        if (!text) continue;
      }
      if (isResumeLikeInterviewerLeak(text)) continue;
    }

    if (text.length > MAX_INTERVIEW_ANSWER_CHARS) {
      text = text.slice(0, MAX_INTERVIEW_ANSWER_CHARS);
    }

    out.push({ role: msg.role, text });
  }

  return out;
}
