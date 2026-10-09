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
  | "session.jt5"
  | "career_watch.cw1"
  | "career_watch.cw2"
  | "career_watch.cw3"
  | "career_watch.cw4"
  | "career_watch.cw5"
  | "notifications.no1"
  | "notifications.no2"
  | "notifications.no3"
  | "notifications.no4"
  | "notifications.no5"
  | "settings.se1"
  | "extension.ex1"
  | "extension.ex2"
  | "extension.ex3"
  | "cover_letter.cl1"
  | "cover_letter.cl2"
  | "cover_letter.cl3"
  | "fit.ft1"
  | "fit.ft2"
  | "fit.ft3"
  | "tracker.tr1"
  | "tracker.tr2"
  | "tracker.tr3"
  | "tracker.tr4"
  | "coach.cc1"
  | "coach.cc2"
  | "coach.cc3"
  | "job_roles.jr1"
  | "job_roles.jr2";

export interface GuidanceContent {
  id: GuidanceStepId;
  title: string;
  body: string;
  /** Longer copy on the /guide reference page. */
  guideBody?: string;
  learnMoreHref?: string;
  learnMoreLabel?: string;
}

export const GUIDANCE_CONTENT: Record<GuidanceStepId, GuidanceContent> = {
  "dashboard.welcome": {
    id: "dashboard.welcome",
    title: "Welcome — quick tour available",
    body:
      "FlintApply works best when you follow a few steps in order: build your master resume, find a job description, then tailor and proofread. Use Tutorial in the top nav for pop-up tips, or open the full Guide anytime from Settings.",
    learnMoreHref: "/guide",
    learnMoreLabel: "Browse all tips",
  },
  "master_resume.mr1": {
    id: "master_resume.mr1",
    title: "Treat this as a one-time setup",
    body:
      "Great start — now treat your master resume as a one-time job. Add correct, complete material: more uploads, real metrics, and accurate titles. We recommend 100+ chunks for strong tailoring. Garbage in, garbage out — this library sets the ceiling for every tailored resume you create. Prefer talking to typing? Try Career coach instead of raw uploads.",
    learnMoreHref: "/profile?mode=story",
    learnMoreLabel: "Try Career coach",
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
      "Your master resume is in good shape. Find a job in FlintApply or save a job description with the browser extension, then start a tailor session. Want alerts instead of searching manually? Set up Career Watch.",
    learnMoreHref: "/career-watch",
    learnMoreLabel: "Set up Career Watch",
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
  "career_watch.cw1": {
    id: "career_watch.cw1",
    title: "What Career Watch actually does",
    body:
      "Career Watch polls a company's ATS board and pulls in every open job it posts — it does not pre-filter by role or seniority. You narrow that down with keywords; without keywords you'll get an alert for every open role at that company.",
  },
  "career_watch.cw2": {
    id: "career_watch.cw2",
    title: "Keywords match title, location, and description",
    body:
      "Keywords are comma-separated and checked as substrings against the job title, job location, and job description — a loose match, not semantic search. \"backend\" matches \"Backend Engineer\" and also a description that merely mentions backend work.",
    guideBody:
      "Matching is substring-based — \"lead\" hits \"Team Lead\" and \"leadership\" in a description. Use distinctive keywords (stack, team name, level like \"senior\") instead of generic ones like \"engineer\" or \"product\" to cut noise.",
  },
  "career_watch.cw3": {
    id: "career_watch.cw3",
    title: "Add location terms if location matters",
    body:
      "There is no separate location filter. If you only want onsite roles in Austin, or only remote roles, add \"austin\", \"remote\", or your state as keywords — otherwise a matching title anywhere can still alert you.",
  },
  "career_watch.cw4": {
    id: "career_watch.cw4",
    title: "Your master resume isn't part of the match",
    body:
      "Career Watch does not read your master resume for relevance — only your keywords against the ATS feed. Tune keywords instead of expecting personalized filtering.",
  },
  "career_watch.cw5": {
    id: "career_watch.cw5",
    title: "Expect multiple alerts per company",
    body:
      "Many roles can match the same keywords in one poll. Dismiss alerts you do not want; that does not affect future matches.",
  },
  "notifications.no1": {
    id: "notifications.no1",
    title: "How notifications work here",
    body:
      "You can get in-app, email, and optional browser push alerts, grouped by category (resume, applications, job alerts, and more). Turn each category on or off per channel below.",
  },
  "notifications.no2": {
    id: "notifications.no2",
    title: "Email and in-app are set per category",
    body:
      "Each row is one category. Check Email, In-app, or both — you do not have to use the same channel for everything.",
  },
  "notifications.no3": {
    id: "notifications.no3",
    title: "Browser push is optional",
    body:
      "Push needs browser permission and is separate from email. If notifications are blocked for this site, use the lock icon in the address bar → Site settings → Notifications → Allow, then Enable again.",
  },
  "notifications.no4": {
    id: "notifications.no4",
    title: "SMS is interview reminders only",
    body:
      "Text messages are limited to interview reminders. Verify your number once; it is reused for later reminders.",
  },
  "notifications.no5": {
    id: "notifications.no5",
    title: "Digest mode batches non-urgent email",
    body:
      "Daily digest bundles non-urgent emails into one message instead of many. Security and payment alerts still send immediately.",
  },
  "settings.se1": {
    id: "settings.se1",
    title: "What lives in Settings",
    body:
      "Settings covers your profile, notification routing, the browser extension, tutorial tips, and account deletion. Channel and category detail lives on the notifications page.",
    learnMoreHref: "/settings/notifications",
    learnMoreLabel: "Notification preferences",
  },
  "extension.ex1": {
    id: "extension.ex1",
    title: "What the extension does",
    body:
      "The extension captures job descriptions from supported job boards (Greenhouse, Lever, and similar) and can autofill forms from your tailored resume. Paste or in-app search work without it.",
  },
  "extension.ex2": {
    id: "extension.ex2",
    title: "Save a JD from the listing page",
    body:
      "On a supported posting, open the Flint icon in your toolbar and save the job — it lands in FlintApply ready to tailor, without copy-paste.",
  },
  "extension.ex3": {
    id: "extension.ex3",
    title: "Autofill uses your tailored resume",
    body:
      "Autofill pulls from the tailored resume for that job — not the full master resume library. Finish tailoring first if fields look generic.",
  },
  "cover_letter.cl1": {
    id: "cover_letter.cl1",
    title: "Pick a session first",
    body:
      "Cover letters are generated from an existing tailor session — choose a recent one, or start tailoring if you do not have one yet.",
    learnMoreHref: "/session/new",
    learnMoreLabel: "Start a tailor session",
  },
  "cover_letter.cl2": {
    id: "cover_letter.cl2",
    title: "It's a draft aligned to the JD",
    body:
      "FlintApply drafts from the JD and your tailored resume. Read it before sending — it does not know your voice or facts you never put in your resume.",
  },
  "cover_letter.cl3": {
    id: "cover_letter.cl3",
    title: "Check company name, role title, and specifics",
    body:
      "Drafts sometimes misstate company or role, or repeat a bullet awkwardly as prose. Proofread those before you send.",
  },
  "fit.ft1": {
    id: "fit.ft1",
    title: "Job fit uses your master resume",
    body:
      "Job fit compares your master resume against a job description you paste — a quick signal before a full tailor session, not a replacement for one.",
  },
  "fit.ft2": {
    id: "fit.ft2",
    title: "The score is directional",
    body:
      "Strong, Good, Partial, or Weak reflects overlap with the JD — not whether you are actually qualified. A low score on a stretch role is not always wrong for you.",
  },
  "fit.ft3": {
    id: "fit.ft3",
    title: "Past analyses are saved",
    body:
      "Every fit check is saved under History so you can revisit without re-pasting the JD.",
  },
  "tracker.tr1": {
    id: "tracker.tr1",
    title: "The board tracks status",
    body:
      "Columns run Draft → Applied → Interviewing → Offer → Accepted, with Rejected and Withdrawn aside. Drag cards to update status; nothing here edits resume content.",
  },
  "tracker.tr2": {
    id: "tracker.tr2",
    title: "Two ways to add an application",
    body:
      "Link a tailored resume from FlintApply, or add manually if you applied elsewhere — both appear on the same board.",
  },
  "tracker.tr3": {
    id: "tracker.tr3",
    title: "Duplicate warnings are a nudge",
    body:
      "A similar company and title already on the board triggers a warning — confirm anyway if it is a different application.",
  },
  "tracker.tr4": {
    id: "tracker.tr4",
    title: "Archive instead of deleting",
    body:
      "Archive hides a card without losing history — toggle Show archived to bring it back.",
  },
  "coach.cc1": {
    id: "coach.cc1",
    title: "Two ways to build by talking",
    body:
      "Tell your story records free-form segments; Coached interview asks structured questions one at a time. Both end by comparing to a job description.",
  },
  "coach.cc2": {
    id: "coach.cc2",
    title: "Coach me is a nudge, not a rewrite",
    body:
      "Coach me flags missing metrics or vague claims — it suggests what to add, not accomplishments to invent. Only add what you can defend.",
  },
  "coach.cc3": {
    id: "coach.cc3",
    title: "Read whole-story feedback before you generate",
    body:
      "Whole-story coach feedback flags gaps across all segments. Read it before generating — fixing here is cheaper than fixing bricks later.",
  },
  "job_roles.jr1": {
    id: "job_roles.jr1",
    title: "Target titles tune in-app search",
    body:
      "Roles you pick here drive FlintApply job search and matching — keep them close to what you would type on a job board, not only aspirational titles.",
  },
  "job_roles.jr2": {
    id: "job_roles.jr2",
    title: "You don't have to pick a role to tailor",
    body:
      "No title fits? Skip this and paste a JD, or save one with the browser extension — tailoring does not require a role selection.",
    learnMoreHref: EXTENSION_INSTALL_PATH,
    learnMoreLabel: "Browser extension",
  },
};
