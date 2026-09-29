/** Extension-captured job descriptions (Strategy B Phase 2). */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ExtensionJobDescription {
  id: string;
  url: string | null;
  title: string | null;
  company: string | null;
  text: string;
  source: string;
  created_at: string;
  session_id: string | null;
}

/** Preserves the HTTP status so callers can show a specific message per cause (I6). */
export class ExtensionJobDescriptionError extends Error {
  constructor(public readonly status: number) {
    super(`Could not load saved job (${status})`);
    this.name = "ExtensionJobDescriptionError";
  }
}

export async function getExtensionJobDescription(
  token: string,
  jdId: string,
): Promise<ExtensionJobDescription> {
  const res = await fetch(`${BASE}/api/job-descriptions/${encodeURIComponent(jdId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ExtensionJobDescriptionError(res.status);
  }
  return res.json() as Promise<ExtensionJobDescription>;
}
