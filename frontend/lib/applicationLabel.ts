/** Dashboard / wizard label from extension or jobs API metadata. */
export function formatApplicationLabel(
  company?: string | null,
  title?: string | null,
): string {
  const c = company?.trim() ?? "";
  const t = title?.trim() ?? "";
  if (c && t) return `${c} — ${t}`;
  return c || t;
}
