import type { BlockingIssue, IssueAnchor, TailoredResumeOutput } from "@/lib/api";

interface TextHit {
  anchor: IssueAnchor;
  score: number;
}

function quotedTerms(text: string): string[] {
  const terms: string[] = [];
  for (const match of text.matchAll(/['"]([^'"]{2,80})['"]/g)) {
    const term = match[1]?.trim();
    if (term) terms.push(term);
  }
  return terms;
}

/** Pull likely resume/JD tokens from issue prose when the model did not attach an anchor. */
export function searchTermsForIssue(issue: BlockingIssue): string[] {
  const raw = `${issue.description} ${issue.suggestion}`;
  const terms = [...quotedTerms(raw)];
  const mirror = raw.match(/Mirror JD vocabulary:\s*['"]([^'"]+)['"]/i);
  if (mirror?.[1]) terms.push(mirror[1]);
  const legacy = raw.match(/vocabulary\s+([A-Za-z][A-Za-z0-9-]{2,})/i);
  if (legacy?.[1]) terms.push(legacy[1]);
  for (const match of raw.matchAll(/\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+)*)\b/g)) {
    const phrase = match[1]?.trim();
    if (!phrase || phrase.length > 40) continue;
    if (/^(Suggestion|Mirror|Bullet|Keyword|Section|Experience|Summary)$/i.test(phrase)) {
      continue;
    }
    terms.push(phrase);
  }
  const seen = new Set<string>();
  const out: string[] = [];
  for (const term of terms) {
    const key = term.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(term);
  }
  return out.slice(0, 8);
}

function scoreHit(term: string, haystack: string, base: number): number {
  const lower = haystack.toLowerCase();
  const needle = term.toLowerCase();
  if (!needle || needle.length < 3) return 0;
  if (lower.includes(needle)) return base + Math.min(needle.length, 20);
  return 0;
}

function hitsFromTerms(terms: string[], tailored: TailoredResumeOutput): TextHit[] {
  const hits: TextHit[] = [];
  if (terms.length === 0) return hits;

  const summary = tailored.summary ?? "";
  for (const term of terms) {
    const s = scoreHit(term, summary, 30);
    if (s > 0) {
      hits.push({ anchor: { section: "summary", entry_index: 0 }, score: s });
    }
  }

  tailored.skills?.forEach((skill, entry_index) => {
    for (const term of terms) {
      const s = scoreHit(term, skill, 25);
      if (s > 0) hits.push({ anchor: { section: "skills", entry_index }, score: s });
    }
  });

  tailored.experience?.forEach((exp, entry_index) => {
    const header = `${exp.title} ${exp.company} ${exp.dates ?? ""}`;
    for (const term of terms) {
      const h = scoreHit(term, header, 22);
      if (h > 0) {
        hits.push({ anchor: { section: "experience", entry_index }, score: h });
      }
    }
    exp.bullets?.forEach((bullet, bullet_index) => {
      for (const term of terms) {
        const b = scoreHit(term, bullet, 40);
        if (b > 0) {
          hits.push({
            anchor: { section: "experience", entry_index, bullet_index },
            score: b,
          });
        }
      }
    });
  });

  tailored.projects?.forEach((raw, entry_index) => {
    const project = raw as { name?: string; description?: string; bullets?: string[] };
    const header = `${project.name ?? ""} ${project.description ?? ""}`;
    for (const term of terms) {
      const s = scoreHit(term, header, 28);
      if (s > 0) hits.push({ anchor: { section: "projects", entry_index }, score: s });
    }
    const bullets = project.bullets ?? [];
    bullets.forEach((bullet, bullet_index) => {
      for (const term of terms) {
        const b = scoreHit(term, bullet, 38);
        if (b > 0) {
          hits.push({
            anchor: { section: "projects", entry_index, bullet_index },
            score: b,
          });
        }
      }
    });
  });

  return hits;
}

/** Best editor anchor for an issue — uses model anchor or resume text search. */
export function resolveIssueAnchor(
  issue: BlockingIssue,
  tailored: TailoredResumeOutput | null | undefined,
): IssueAnchor | null {
  if (issue.anchor) return issue.anchor;
  if (!tailored) return null;

  const terms = searchTermsForIssue(issue);
  const hits = hitsFromTerms(terms, tailored);
  if (/summary/i.test(issue.suggestion)) {
    hits.push({ anchor: { section: "summary", entry_index: 0 }, score: 55 });
  }
  if (/skills/i.test(issue.suggestion)) {
    hits.push({ anchor: { section: "skills", entry_index: 0 }, score: 42 });
  }
  if (hits.length === 0) {
    if (issue.category === "bullet" || issue.category === "metric") {
      return { section: "experience", entry_index: 0, bullet_index: 0 };
    }
    if (issue.category === "keyword" || issue.category === "section") {
      return { section: "skills", entry_index: 0 };
    }
    return { section: "summary", entry_index: 0 };
  }
  hits.sort((a, b) => b.score - a.score);
  return hits[0]!.anchor;
}

export function locateIssueHint(issue: BlockingIssue, tailored: TailoredResumeOutput | null): string | null {
  if (issue.suggestion.includes("In the JD they use it like:")) {
    return null;
  }
  if (issue.anchor) return null;
  const terms = searchTermsForIssue(issue);
  if (terms.length === 0) return "Showing the closest section — adjust wording there.";
  const anchor = resolveIssueAnchor(issue, tailored);
  if (!anchor) return null;
  const term = terms[0];
  if (term && tailored) {
    const blob = JSON.stringify(tailored).toLowerCase();
    if (!blob.includes(term.toLowerCase())) {
      return `Could not find “${term}” in the resume — this may be JD tone guidance. Showing the closest section.`;
    }
  }
  return null;
}
