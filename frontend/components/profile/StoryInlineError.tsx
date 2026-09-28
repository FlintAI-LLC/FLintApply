"use client";

import { EmailVerificationCallout } from "@/components/auth/EmailVerificationCallout";

interface Props {
  error: string | null;
  errorCode: string | null;
}

export function StoryInlineError({ error, errorCode }: Props) {
  if (errorCode === "email_verification_required") {
    return <EmailVerificationCallout />;
  }
  if (!error) return null;
  return (
    <p className="text-red-700 dark:text-red-400 text-xs bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
      {error}
    </p>
  );
}

function storyErrorFromUnknown(err: unknown): { message: string; code: string | null } {
  if (err instanceof Error) {
    const code = (err as Error & { code?: string }).code ?? null;
    return { message: err.message, code };
  }
  return { message: "Something went wrong. Please try again.", code: null };
}

export { storyErrorFromUnknown };
