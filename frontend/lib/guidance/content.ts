import { EXTENSION_INSTALL_PATH } from "@/lib/extensionInstall";

export type GuidanceStepId =
  | "dashboard.welcome"
  | "master_resume.mr1"
  | "master_resume.mr2"
  | "master_resume.mr3"
  | "master_resume.mr4"
  | "master_resume.mr5"
  | "jobs.js1"
  | "jobs.js2"
  | "jobs.js3"
  | "jobs.js4"
  | "jobs.js5"
  | "session.jt1"
  | "session.jt1b"
  | "session.jt2a"
  | "session.jt2b"
  | "session.jt2c"
  | "session.jt2d"
  | "session.jt3"
  | "session.jt4"
  | "session.jt5";

export interface GuidanceContent {
  id: GuidanceStepId;
  title: string;
  body: string;
  learnMoreHref?: string;
  learnMoreLabel?: string;
}

export const GUIDANCE_CONTENT: Record<GuidanceStepId, GuidanceContent> = {
  "dashboard.welcome": {
    id: "dashboard.welcome",
    title: "Welcome — quick tour available",
    body:
      "FlintApply works best when you follow a few steps in order: build your master resume, find a job description, then tailor and proofread. Use the Tutorial control in the top nav for step-by-step tips. Turn Tutorial off when you no longer want pop-up reminders.",
  },
  "master_resume.mr1": {
    id: "master_resume.mr1",
    title: "Treat this as a one-time setup",
    body:
      "Great start — now treat your master resume as a one-time job. Add correct, complete material: more uploads, real metrics, and accurate titles. We recommend 100+ chunks for strong tailoring. Garbage in, garbage out — this library sets the ceiling for every tailored resume you create.",
  },
  "master_resume.mr2": {
    id: "master_resume.mr2",
    title: "Remove duplicates",
    body:
      "Multiple uploads often create duplicate project, education, or skill chunks. Click Remove duplicates to keep the richest version of each.",
  },
  "master_resume.mr3": {
    id: "master_resume.mr3",
    title: "Organize by section",
    body:
      "You have enough chunks. Open Manage bricks by section to review how your experience is grouped.",
    learnMoreHref: "/profile/bricks",
    learnMoreLabel: "Manage bricks",
  },
  "master_resume.mr4": {
    id: "master_resume.mr4",
    title: "Review every brick",
    body:
      "Read each brick. Edit anything that is wrong, incomplete, or still AI-generated. This is your last quality gate before tailoring — fix it now so you are not fixing the same mistakes on every job.",
  },
  "master_resume.mr5": {
    id: "master_resume.mr5",
    title: "Master resume ready",
    body:
      "Your master resume is in good shape. Find a job in FlintApply or save a job description with the browser extension, then start a tailor session.",
    learnMoreHref: EXTENSION_INSTALL_PATH,
    learnMoreLabel: "Install extension",
  },
  "jobs.js1": {
    id: "jobs.js1",
    title: "Find jobs to tailor for",
    body:
      "Use the search form to look for roles — enter a job title or keywords and run Search. Pick filters (location, remote, date posted) that match your goals.",
  },
  "jobs.js2": {
    id: "jobs.js2",
    title: "Bookmark jobs you like",
    body:
      "Review the results. For any job you might apply to, click Bookmark on the card. Saved jobs stay in your Saved tab so you can tailor later.",
  },
  "jobs.js3": {
    id: "jobs.js3",
    title: "Search outside FlintApply too",
    body:
      "If nothing fits here, search on LinkedIn, Indeed, or company sites — then install the Flint browser extension and save the job description from the listing page.",
    learnMoreHref: EXTENSION_INSTALL_PATH,
    learnMoreLabel: "Extension install guide",
  },
  "jobs.js4": {
    id: "jobs.js4",
    title: "Start tailoring",
    body:
      "Open the Saved tab or click Tailor Resume on a bookmarked job. FlintApply uses the job description plus your master resume to build a tailored version.",
  },
  "jobs.js5": {
    id: "jobs.js5",
    title: "Set your target roles",
    body:
      "Add preferred job titles so keyword and match search work better. Keep titles close to what you search for on job boards.",
  },
  "session.jt1": {
    id: "session.jt1",
    title: "Use a complete job description",
    body:
      "Tailoring needs the full JD — requirements, responsibilities, and keywords. If you saved the job from search or the extension, confirm the description looks complete. Thin JDs produce weak resumes.",
    learnMoreHref: EXTENSION_INSTALL_PATH,
    learnMoreLabel: "Extension guide",
  },
  "session.jt1b": {
    id: "session.jt1b",
    title: "Read the audit — then you edit",
    body:
      "Keyword gaps show what the JD asks for vs what was found — not a command to stuff every term in. Contact issues flag unprofessional emails, not firstname@yourdomain when your header name differs slightly. Fix bullet issues that matter for this role.",
  },
  "session.jt2a": {
    id: "session.jt2a",
    title: "Your rewrite is a draft",
    body:
      "FlintApply pulled bullets from your master resume and matched JD language. This is not ready to send. Read every section yourself before Score & Export.",
  },
  "session.jt2b": {
    id: "session.jt2b",
    title: "What to check on this page",
    body:
      "Verify company names, titles, dates, and bullets. Add real metrics you can defend. Missing keywords are aspirational — only add skills you truly have evidence for. Use Edit icons; you do not need chat for most fixes.",
  },
  "session.jt2c": {
    id: "session.jt2c",
    title: "Re-tailor sparingly",
    body:
      "Re-tailor from scratch costs a credit and re-runs the full pipeline. Use it if the draft is structurally wrong. Full re-analysis on Export is for fresh ATS issue text — not needed if the score already matches.",
  },
  "session.jt2d": {
    id: "session.jt2d",
    title: "Last check before scoring",
    body:
      "Confirm contact info, no placeholder metrics, employers and dates accurate, and page length sensible. If something is wrong, go back and edit — scoring frozen issues is cheaper than fixing a bad PDF later.",
  },
  "session.jt3": {
    id: "session.jt3",
    title: "Score is a mirror, not a grade",
    body:
      "Read Resume quality vs Role fit separately. Dismiss keyword fixes for skills you do not have. Apply all uses one batch — it can stuff keywords and hurt readability. Fix export blockers on Rewrite first, then Recalculate ATS (free).",
  },
  "session.jt4": {
    id: "session.jt4",
    title: "Proofread automated changes",
    body:
      "We applied batch fixes for ATS keywords. Automated edits can sound awkward. Re-read Summary, Skills, and Experience — correct anything inaccurate.",
  },
  "session.jt5": {
    id: "session.jt5",
    title: "Final human check",
    body:
      "Last step: verify contact info, company names, numbers, and page length. You are responsible for what you send — AI assists, you approve.",
  },
};
