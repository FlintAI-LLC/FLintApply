import type { TailoredResumeOutput } from "@/lib/api";

/** Mirrors backend `output_linter.py` skill rules for client-side checks. */
const SKILL_FUNCTION_WORD_RE =
  /\b(with|of|in|the|a|to|that|which|for|and|or|by|from|as|at)\b/gi;
const ORPHAN_SKILL_CONJUNCTION = /^(and|or)\b/i;
const TERMINAL_PUNCT = new Set([".", ",", ";", ":", "!", "?"]);

export type TailoredLintIssue = {
  field: "skills" | "bullets";
  index: number;
  rule: string;
  original: string;
};

function flattenSkillTerms(skills: string[]): string[] {
  const terms: string[] = [];
  for (const line of skills) {
    const payload = line.includes(":") ? line.split(":", 2)[1]! : line;
    for (const part of payload.split(",")) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      if (ORPHAN_SKILL_CONJUNCTION.test(trimmed) && terms.length > 0) {
        terms[terms.length - 1] = `${terms[terms.length - 1]} ${trimmed}`;
      } else {
        terms.push(trimmed);
      }
    }
  }
  return terms;
}

export function skillIsSentence(skill: string): boolean {
  const candidate = skill.trim();
  if (!candidate) return false;
  if (candidate.length > 40) return true;
  if (TERMINAL_PUNCT.has(candidate[candidate.length - 1]!)) return true;
  if (ORPHAN_SKILL_CONJUNCTION.test(candidate)) return true;
  const words = candidate.split(/\s+/);
  if (words.length >= 8) return true;
  const functionWordHits = (candidate.match(SKILL_FUNCTION_WORD_RE) ?? []).length;
  return functionWordHits >= 2;
}

function skillIsJdSubstring(skill: string, jdLower: string): boolean {
  if (!jdLower) return false;
  const skillN = skill.toLowerCase().trim();
  const words = skillN.split(/\s+/);
  if (words.length < 5) return false;
  if (jdLower.includes(skillN)) return true;
  const jdWords = jdLower.split(/\s+/);
  if (jdWords.length < 5) return false;
  for (let i = 0; i <= jdWords.length - 5; i++) {
    const window = jdWords.slice(i, i + 5).join(" ");
    if (skillN === window) return true;
  }
  return false;
}

export function isValidSkillKeyword(term: string, jdText = ""): boolean {
  const candidate = term.trim();
  if (!candidate) return false;
  if (skillIsSentence(candidate)) return false;
  if (jdText && skillIsJdSubstring(candidate, jdText.toLowerCase())) return false;
  return true;
}

export function blockingSkillLintIssues(
  skills: string[],
  jdText = "",
): TailoredLintIssue[] {
  const flat = flattenSkillTerms(skills);
  const issues: TailoredLintIssue[] = [];
  const jdLower = jdText.toLowerCase();
  for (let index = 0; index < flat.length; index++) {
    const skill = flat[index]!;
    if (skillIsSentence(skill)) {
      issues.push({
        field: "skills",
        index,
        rule: "skill_is_sentence",
        original: skill,
      });
    } else if (skillIsJdSubstring(skill, jdLower)) {
      issues.push({
        field: "skills",
        index,
        rule: "skill_is_jd_substring",
        original: skill,
      });
    }
  }
  return issues;
}

/** Remove skill terms that would fail server lint (e.g. after Apply all). */
export function stripBlockingSkillTerms(
  tailored: TailoredResumeOutput,
  jdText = "",
): TailoredResumeOutput {
  const skills = tailored.skills ?? [];
  if (skills.length === 0) return tailored;

  const nextLines: string[] = [];
  for (const line of skills) {
    const idx = line.indexOf(":");
    if (idx < 0) {
      if (isValidSkillKeyword(line, jdText)) nextLines.push(line);
      continue;
    }
    const prefix = line.slice(0, idx + 1);
    const rest = line.slice(idx + 1);
    const kept = rest
      .split(",")
      .map((part) => part.trim())
      .filter((part) => part && isValidSkillKeyword(part, jdText));
    if (kept.length > 0) {
      nextLines.push(`${prefix} ${kept.join(", ")}`);
    }
  }

  return { ...tailored, skills: nextLines };
}

export function formatTailoredLintErrors(
  fieldErrors: Array<{ field: string; rule: string; original: string }>,
): string {
  if (fieldErrors.length === 0) {
    return "Resume contains invalid bullets or skills";
  }
  const lines = fieldErrors.slice(0, 5).map((err) => {
    const snippet =
      err.original.length > 80 ? `${err.original.slice(0, 80)}…` : err.original;
    return `• ${err.field} (${err.rule}): “${snippet}”`;
  });
  const more =
    fieldErrors.length > 5 ? `\n…and ${fieldErrors.length - 5} more.` : "";
  return `Resume contains invalid bullets or skills. Remove or shorten:\n${lines.join("\n")}${more}`;
}
