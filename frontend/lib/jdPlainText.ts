/** Convert extension-captured HTML JD bodies to plain text for the wizard. */
export function plainTextFromMaybeHtml(text: string): string {
  const trimmed = text.trim();
  if (!trimmed || !/<[a-z][\s\S]*>/i.test(trimmed)) return trimmed;
  if (typeof DOMParser === "undefined") {
    return trimmed
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }
  const doc = new DOMParser().parseFromString(trimmed, "text/html");
  return (doc.body.textContent ?? trimmed)
    .replace(/\r\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
}
