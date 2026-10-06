"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { AlertCircle } from "lucide-react";
import { getExtensionJobDescription } from "@/lib/extensionJobDescription";
import {
  captureExtensionHandoffFromParams,
  clearExtensionHandoff,
  getExtensionHandoff,
  markExtensionHandoffConsumed,
  saveExtensionHandoff,
  replaceSessionNewUrlIfNeeded,
} from "@/lib/extensionHandoff";
import { classifyJdLoadError, EMPTY_JD_TEXT_ERROR, type JdLoadError } from "@/lib/jdLoadError";
import { expiredSessionAuthUrl } from "@/lib/auth/accessToken";
import { saveAuthReturnUrl } from "@/lib/auth/returnUrl";
import { clearCheckupHandoff, getCheckupHandoff } from "@/lib/checkupHandoff";
import { formatApplicationLabel } from "@/lib/applicationLabel";
import { shouldReviewExtensionJd } from "@/lib/jdCompleteness";
import { plainTextFromMaybeHtml } from "@/lib/jdPlainText";
import { PRODUCT_NAME } from "@/lib/brand";
import { getJob } from "@/lib/jobs";
import { ResumeUploader } from "@/components/wizard/ResumeUploader";
import { UserInfoForm } from "@/components/wizard/UserInfoForm";
import { JDInput } from "@/components/wizard/JDInput";
import {
  createSession,
  saveApplicationLabel,
  saveUserInfo,
  submitJD,
  checkSession,
  pasteResumeText,
  type JDPayload,
  type ParsedResume,
  type UserInfoPayload,
} from "@/lib/api";

const SESSION_STORAGE_KEY = "smart_resume_session_id";
const APP_NAME_STORAGE_KEY = "smart_resume_application_name";
const APP_NAME_JD_KEY = "smart_resume_application_name_jd_id";

// Resume → Job Description → Your Info (platform AI — no BYOK step)
const STEPS = ["resume", "jd", "info"] as const;
type Step = (typeof STEPS)[number];

const STEP_LABELS: Record<Step, string> = {
  resume: "Upload Resume",
  jd:     "Job Description",
  info:   "Your Info",
};

function NewSessionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [step, setStep] = useState<Step>((searchParams.get("step") as Step) ?? "resume");

  // Carry forward between steps
  const [parsedResume, setParsedResume] = useState<ParsedResume | null>(null);
  const [jdText, setJdText] = useState("");
  const [jdTitle, setJdTitle] = useState<string | null>(null);
  const [jdSourceUrl, setJdSourceUrl] = useState<string | null>(null);
  const [jdReviewRecommended, setJdReviewRecommended] = useState(false);
  const [infoHydrating, setInfoHydrating] = useState(false);
  const [applicationName, setApplicationName] = useState("");
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  // Specific, actionable failure for the extension/jobs JD fetch (I6) — never
  // a silent blank textarea. `jdRetryNonce` re-triggers the load effect for
  // the error banner's "Try again" action without waiting on token/param changes.
  const [jdLoadError, setJdLoadError] = useState<JdLoadError | null>(null);
  const [jdRetryNonce, setJdRetryNonce] = useState(0);
  // True while the JD fetch effect is in flight (initial load or retry) —
  // drives a pending state so clearing jdLoadError on retry doesn't leave
  // the user with neither the stale banner nor any indication anything is
  // happening.
  const [jdLoadPending, setJdLoadPending] = useState(false);

  const [loading, setLoading] = useState(false);
  const jdLoadedRef = useRef(false);
  const jobsJdPersistedRef = useRef(false);
  const applicationNameDirtyRef = useRef(false);
  const jdAutoRefetchRef = useRef(false);
  const checkupResumeAppliedRef = useRef(false);
  const sessionBootstrapRef = useRef(false);
  const appNameRestoredRef = useRef(false);
  const lastPersistedNameRef = useRef<string | null>(null);
  const [hasMasterResume, setHasMasterResume] = useState<boolean | undefined>(undefined);

  // Restore extension handoff if OAuth stripped jd_id from the URL.
  useEffect(() => {
    const urlHandoff = captureExtensionHandoffFromParams(searchParams);
    if (urlHandoff) return;
    // ?fresh=1 ("Tailor for a new job" from the dashboard) must never
    // resurrect a stale handoff from a previous tailoring run (defect #7).
    if (searchParams.get("fresh") === "1") return;

    const stored = getExtensionHandoff();
    if (stored && !searchParams.get("jd_id")) {
      replaceSessionNewUrlIfNeeded(router, stored);
    }
  }, [searchParams, router]);

  // Restore application label from sessionStorage once (survives refresh mid-wizard).
  useEffect(() => {
    if (appNameRestoredRef.current) return;
    const storedName = sessionStorage.getItem(APP_NAME_STORAGE_KEY);
    if (!storedName) return;
    appNameRestoredRef.current = true;
    setApplicationName((prev) => (prev.trim() || applicationNameDirtyRef.current ? prev : storedName));
    if (!applicationNameDirtyRef.current) {
      lastPersistedNameRef.current = storedName;
    }
  }, []);

  const hydrateWizardFromSession = (
    snap: Awaited<ReturnType<typeof checkSession>>,
  ) => {
    if (snap.resume_parsed) setParsedResume(snap.resume_parsed);
    if (snap.jd_raw?.trim()) setJdText(snap.jd_raw);
    const label = snap.application_display_name?.trim();
    if (label) {
      setApplicationName((prev) => (prev.trim() ? prev : label));
      sessionStorage.setItem(APP_NAME_STORAGE_KEY, label);
      lastPersistedNameRef.current = label;
    }
  };

  // Bootstrap wizard session once — resume in-progress runs unless ?fresh=1.
  useEffect(() => {
    if (sessionBootstrapRef.current) return;
    sessionBootstrapRef.current = true;

    void (async () => {
      setBootstrapError(null);
      const forceFresh = searchParams.get("fresh") === "1";
      const continueId = searchParams.get("continue");
      const urlStep = searchParams.get("step") as Step | null;
      const editingJd = urlStep === "jd";

      const tryRestore = async (id: string): Promise<boolean> => {
        try {
          const snap = await checkSession(id);
          if (snap.phase1_complete && !editingJd) {
            router.replace(`/session/${id}?step=analysis`);
            return true;
          }
          setSessionId(id);
          sessionStorage.setItem(SESSION_STORAGE_KEY, id);
          hydrateWizardFromSession(snap);
          return true;
        } catch {
          return false;
        }
      };

      if (!forceFresh) {
        const candidate =
          continueId ?? sessionStorage.getItem(SESSION_STORAGE_KEY);
        if (candidate && (await tryRestore(candidate))) {
          return;
        }
        if (candidate) {
          sessionStorage.removeItem(SESSION_STORAGE_KEY);
        }
      } else {
        sessionStorage.removeItem(SESSION_STORAGE_KEY);
        sessionStorage.removeItem(APP_NAME_STORAGE_KEY);
        lastPersistedNameRef.current = null;
      }

      try {
        const r = await createSession();
        setSessionId(r.session_id);
        sessionStorage.setItem(SESSION_STORAGE_KEY, r.session_id);
      } catch {
        setBootstrapError(
          "Could not start a tailoring session. Check that the API is running and try again.",
        );
      }
    })();
  }, [searchParams, router]);

  // Deep-link query params (paste JD, checkup funnel) — may change without new session.
  useEffect(() => {
    const jdFromQuery = searchParams.get("jd");
    if (jdFromQuery) {
      try {
        setJdText(decodeURIComponent(jdFromQuery));
        setStep("jd");
      } catch {
        setJdText(jdFromQuery);
        setStep("jd");
      }
      return;
    }

    if (searchParams.get("from") === "checkup") {
      const handoff = getCheckupHandoff();
      if (handoff) {
        let jd = handoff.jdText;
        const title = handoff.jobTitle.trim();
        if (title && !jd.toLowerCase().includes(title.toLowerCase())) {
          jd = `${title}\n\n${jd}`;
        }
        setJdText(jd);
        setStep("jd");
        if (handoff.resumeText.trim()) {
          sessionStorage.setItem("sr_checkup_resume_text", handoff.resumeText);
        }
        clearCheckupHandoff();
      }
    }
  }, [searchParams]);

  // Checkup funnel: auto-apply resume text saved before auth redirect.
  useEffect(() => {
    if (!sessionId || checkupResumeAppliedRef.current) return;
    const resumeText = sessionStorage.getItem("sr_checkup_resume_text");
    if (!resumeText?.trim()) return;
    checkupResumeAppliedRef.current = true;
    void (async () => {
      try {
        const result = await pasteResumeText(sessionId, resumeText);
        setParsedResume(result.parsed);
        sessionStorage.removeItem("sr_checkup_resume_text");
      } catch {
        // User can still upload manually on the resume step.
      }
    })();
  }, [sessionId]);

  // Separate effect: load JD from extension or jobs API once the backend token
  // is available. Runs when token arrives (may be after the init effect above).
  const backendToken = session?.backendAccessToken;
  useEffect(() => {
    if (!backendToken) return;
    let cancelled = false;

    const urlJdId = searchParams.get("jd_id");
    // ?fresh=1 ("Tailor for a new job" from the dashboard) must never
    // resurrect a stale extension handoff from a previous run (defect #7).
    const isFreshStart = searchParams.get("fresh") === "1";
    const storedHandoff = isFreshStart ? null : getExtensionHandoff();
    const jdId = urlJdId ?? storedHandoff?.jd_id ?? null;
    const jdSource = searchParams.get("source") ?? storedHandoff?.source ?? "extension";
    const jdReviewFlag =
      searchParams.get("jd_review") === "1" || storedHandoff?.jd_review === true;

    if (jdId && !urlJdId) {
      const handoff = {
        jd_id: jdId,
        source: jdSource,
        step: storedHandoff?.step ?? "jd",
        jd_review: jdReviewFlag,
        // Carry the original capture time forward — rebuilding this object
        // without it made saveExtensionHandoff stamp a fresh Date.now() on
        // every re-save, renewing the 30-minute TTL indefinitely (S1).
        captured_at: storedHandoff?.captured_at,
      };
      saveExtensionHandoff(handoff);
      replaceSessionNewUrlIfNeeded(router, handoff);
    }

    void (async () => {
      try {
        const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const res = await fetch(`${BASE}/api/profile/resume`, {
          headers: { Authorization: `Bearer ${backendToken}` },
        });
        if (cancelled) return;
        if (res.ok) {
          const profile = await res.json() as { chunk_count?: number };
          setHasMasterResume((profile.chunk_count ?? 0) > 0);
        } else {
          setHasMasterResume(false);
        }
      } catch {
        if (!cancelled) setHasMasterResume(false);
      }
    })();

    // Only load the JD once. Subsequent searchParams changes (e.g. goTo("info")
    // changing the URL) must not reset the wizard back to the JD step. Note
    // jdLoadedRef only ever latches inside the success branches below, so a
    // failed attempt (any jdLoadError kind) always leaves it retryable — and
    // the `cancelled` cleanup below still runs even when this guard skips the
    // fetch, so the hasMasterResume request above cannot set stale state.
    if (jdId && !jdLoadedRef.current) {
      setJdLoadPending(true);
      void (async () => {
        try {
          if (jdSource === "extension") {
            const saved = await getExtensionJobDescription(backendToken, jdId);
            if (cancelled) return;
            setJdSourceUrl(saved.url);

            if (!saved.text?.trim()) {
              // Captured, but with no text — a distinct, actionable message,
              // never a bare blank textarea (defect #2 / I6).
              setJdLoadError(EMPTY_JD_TEXT_ERROR);
              return;
            }

            // Resume only when the linked session finished the wizard (info saved
            // or keywords already run). A JD-only link would hijack refresh mid-flow.
            if (saved.session_id) {
              try {
                const snap = await checkSession(saved.session_id);
                if (cancelled) return;
                if (snap.has_user_info || snap.phase1_complete) {
                  jdLoadedRef.current = true;
                  setJdLoadError(null);
                  clearExtensionHandoff();
                  markExtensionHandoffConsumed(jdId);
                  router.replace(`/session/${saved.session_id}?step=analysis`);
                  return;
                }
              } catch {
                if (cancelled) return;
                // Session expired — continue wizard with this JD text.
              }
            }

            jdLoadedRef.current = true;
            setJdLoadError(null);
            setJdReviewRecommended(
              shouldReviewExtensionJd(jdSource, saved.url, jdReviewFlag),
            );
            setJdText(plainTextFromMaybeHtml(saved.text));
            if (saved.title?.trim()) {
              setJdTitle(saved.title.trim());
            }
            const suggestedName = formatApplicationLabel(saved.company, saved.title);
            const lastNamedJdId = sessionStorage.getItem(APP_NAME_JD_KEY);
            if (suggestedName && lastNamedJdId !== jdId) {
              sessionStorage.setItem(APP_NAME_JD_KEY, jdId);
              sessionStorage.setItem(APP_NAME_STORAGE_KEY, suggestedName);
              lastPersistedNameRef.current = suggestedName;
              setApplicationName(suggestedName);
            } else if (suggestedName) {
              setApplicationName((prev) => (prev.trim() ? prev : suggestedName));
            }
            const urlStep = searchParams.get("step");
            const onLaterWizardStep = urlStep === "info" || urlStep === "resume";
            if (!onLaterWizardStep) {
              setStep("jd");
              const reviewRecommended = shouldReviewExtensionJd(
                jdSource,
                saved.url,
                jdReviewFlag,
              );
              replaceSessionNewUrlIfNeeded(router, {
                jd_id: jdId,
                source: jdSource,
                step: "jd",
                jd_review: reviewRecommended,
              });
            }
            // JD is now loaded into wizard state — consume the handoff so it
            // cannot hijack a later "Tailor for a new job" run and so the
            // dashboard banner disappears (defect #6/#9). Marking it consumed
            // (keyed by jd_id) also stops captureExtensionHandoffFromParams —
            // which re-runs on every step transition since jd_id stays in the
            // URL — from writing the same handoff straight back to storage on
            // the very next render (AC9).
            clearExtensionHandoff();
            markExtensionHandoffConsumed(jdId);
            return;
          }
          const job = await getJob(backendToken, jdId);
          if (cancelled) return;
          if (!job.description?.trim()) {
            setJdLoadError(EMPTY_JD_TEXT_ERROR);
            return;
          }
          jdLoadedRef.current = true;
          setJdLoadError(null);
          setJdText(job.description);
          if (job.title?.trim()) {
            setJdTitle(job.title.trim());
          }
          setStep("jd");
          replaceSessionNewUrlIfNeeded(router, {
            jd_id: jdId,
            source: "jobs",
            step: "jd",
          });
        } catch (err) {
          if (cancelled) return;
          // Every failure path (401 / 404 / network / server error) gets a
          // distinct, actionable message — never the bare silent catch this
          // replaced (defect #1 / I6).
          const classified = classifyJdLoadError(err);
          setJdLoadError(classified);
          if (classified.kind === "not_found") {
            // This jd_id will keep 404ing for up to EXTENSION_HANDOFF_TTL_MS —
            // don't leave the dashboard banner offering "Continue tailoring"
            // into the same wall (S2).
            clearExtensionHandoff();
            markExtensionHandoffConsumed(jdId);
          }
        } finally {
          if (!cancelled) setJdLoadPending(false);
        }
      })();
    }

    return () => {
      cancelled = true;
    };
  }, [backendToken, searchParams, router, jdRetryNonce]);

  useEffect(() => {
    const jdId = searchParams.get("jd_id");
    if (!jdId || jdText.trim() || !backendToken) return;
    if (jdAutoRefetchRef.current) return;
    jdAutoRefetchRef.current = true;
    jdLoadedRef.current = false;
    setJdRetryNonce((n) => n + 1);
  }, [backendToken, searchParams, jdText]);

  // Jobs handoff: persist JD to the session as soon as we have text + session id.
  useEffect(() => {
    const source = searchParams.get("source");
    const jdId = searchParams.get("jd_id");
    if (source !== "jobs" || !jdId || !sessionId || !jdText.trim()) return;
    if (jobsJdPersistedRef.current) return;

    let cancelled = false;
    void (async () => {
      try {
        const snap = await checkSession(sessionId);
        if (cancelled) return;
        if (snap.has_jd) {
          jobsJdPersistedRef.current = true;
          return;
        }
        await submitJD(sessionId, {
          jd_text: jdText,
          jd_id: jdId,
        });
        if (!cancelled) jobsJdPersistedRef.current = true;
      } catch {
        // User can still submit on the JD step.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId, jdText, jdTitle, searchParams]);

  const goTo = (s: Step) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", s);
    params.delete("fresh");
    const handoff = getExtensionHandoff();
    const jdId = searchParams.get("jd_id") ?? handoff?.jd_id;
    const jdSource = searchParams.get("source") ?? handoff?.source;
    const jdReview = searchParams.get("jd_review") === "1" || handoff?.jd_review === true;
    if (jdId) params.set("jd_id", jdId);
    if (jdSource) params.set("source", jdSource);
    if (jdReview) params.set("jd_review", "1");
    else params.delete("jd_review");
    setStep(s);
    router.replace(`/session/new?${params.toString()}`);
  };

  const persistApplicationName = async (name: string) => {
    const trimmed = name.trim();
    if (!trimmed || trimmed === lastPersistedNameRef.current) return;
    sessionStorage.setItem(APP_NAME_STORAGE_KEY, trimmed);
    lastPersistedNameRef.current = trimmed;
    if (!sessionId) return;
    try {
      await saveApplicationLabel(sessionId, trimmed);
    } catch {
      // Best-effort — wizard can continue; dashboard sync retries on JD submit.
    }
  };

  const applicationNameField = (
    <div className="mb-6">
      <label className="block text-slate-600 dark:text-slate-400 text-xs mb-1 font-medium">
        Application name *
      </label>
      <input
        value={applicationName}
        autoComplete="off"
        onChange={(e) => {
          applicationNameDirtyRef.current = true;
          setApplicationName(e.target.value);
        }}
        onBlur={() => {
          if (applicationName.trim()) {
            void persistApplicationName(applicationName);
          }
        }}
        placeholder="e.g. Acme Health — Senior Backend Engineer"
        className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 placeholder-slate-600"
      />
    </div>
  );

  // Browser back/forward (and explicit "New session" clicks): keep wizard
  // step aligned with the URL.  A missing ?step= param means the user
  // navigated to /session/new fresh — reset to the first step so the wizard
  // doesn't stay frozen on whatever step it was on before.
  useEffect(() => {
    const raw = searchParams.get("step");
    if (!raw || !STEPS.includes(raw as Step)) {
      // If a jd_id is present, the token effect will set step once the JD
      // loads and push ?step=jd into the URL. Resetting here would race.
      if (searchParams.get("jd_id")) return;
      // goTo() updates step before ?step= lands — never wipe sessionId here.
      if (sessionId) return;
      if (step !== "resume") {
        setStep("resume");
        setParsedResume(null);
        if (!searchParams.get("jd_id")) {
          setJdText("");
        }
      }
      return;
    }
    const urlStep = raw as Step;
    if (urlStep !== step) setStep(urlStep);
  }, [searchParams, step, sessionId]);

  // Hydrate resume parse state when landing on info (refresh or master import).
  useEffect(() => {
    if (step !== "info" || !sessionId || parsedResume) return;

    let cancelled = false;
    setInfoHydrating(true);
    void (async () => {
      try {
        const snapshot = await checkSession(sessionId);
        if (cancelled) return;
        if (snapshot.resume_parsed) {
          setParsedResume(snapshot.resume_parsed);
          return;
        }

        if (!backendToken) return;
        const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const res = await fetch(`${BASE}/api/profile/resume`, {
          headers: { Authorization: `Bearer ${backendToken}` },
        });
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as { raw_text?: string };
        if (!data.raw_text?.trim()) return;
        const result = await pasteResumeText(sessionId, data.raw_text);
        if (!cancelled) setParsedResume(result.parsed);
      } catch {
        // User can fill the form manually or go back to upload resume.
      } finally {
        if (!cancelled) setInfoHydrating(false);
      }
    })();

    return () => {
      cancelled = true;
      setInfoHydrating(false);
    };
  }, [step, sessionId, parsedResume, backendToken]);

  // If user backs into the wizard after finishing, skip to the live session.
  useEffect(() => {
    if (step !== "info" || !sessionId) return;
    let cancelled = false;
    checkSession(sessionId)
      .then((s) => {
        if (!cancelled && s.phase1_complete) {
          router.replace(`/session/${sessionId}?step=analysis`);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [step, sessionId, router]);

  const handleResumeParsed = async (parsed: ParsedResume) => {
    setParsedResume(parsed);
    if (applicationName.trim()) {
      await persistApplicationName(applicationName);
    }
    if (!sessionId) {
      goTo("jd");
      return;
    }
    try {
      const snap = await checkSession(sessionId);
      goTo(snap.has_jd ? "info" : "jd");
    } catch {
      goTo("jd");
    }
  };

  // JD submitted → save to backend, store text locally, advance to next step.
  // In the extension flow the user lands directly on JD having skipped resume
  // upload, so we redirect them to "resume" next. In the normal flow they
  // already uploaded a resume (parsedResume is set) or have a master resume
  // saved, so we can go straight to "info".
  const handleJD = async (payload: JDPayload) => {
    if (!sessionId) return;
    setLoading(true);
    try {
      if (applicationName.trim()) {
        await persistApplicationName(applicationName);
      }
      const result = await submitJD(sessionId, payload);
      if (result.jd_text) setJdText(result.jd_text);
      else if (payload.jd_text) setJdText(payload.jd_text);
      setJdTitle(result.jd_title ?? null);

      let resumeData: ParsedResume | null = parsedResume;

      if (!resumeData) {
        try {
          const snapshot = await checkSession(sessionId);
          if (snapshot.resume_parsed) {
            resumeData = snapshot.resume_parsed;
          }
        } catch {
          // continue to profile import
        }
      }

      if (!resumeData && backendToken) {
        try {
          const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
          const res = await fetch(`${BASE}/api/profile/resume`, {
            headers: { Authorization: `Bearer ${backendToken}` },
          });
          if (res.ok) {
            const data = (await res.json()) as { raw_text?: string };
            if (data.raw_text?.trim()) {
              const result = await pasteResumeText(sessionId, data.raw_text);
              resumeData = result.parsed;
            }
          }
        } catch {
          // fall through to resume upload step
        }
      }

      let hasUserInfo = false;
      try {
        const afterJd = await checkSession(sessionId);
        hasUserInfo = !!afterJd.has_user_info;
      } catch {
        // continue to wizard routing
      }

      if (resumeData) {
        setParsedResume(resumeData);
        if (hasUserInfo) {
          sessionStorage.removeItem(SESSION_STORAGE_KEY);
          sessionStorage.removeItem(APP_NAME_STORAGE_KEY);
          router.replace(`/session/${sessionId}?step=analysis`);
        } else {
          goTo("info");
        }
      } else {
        goTo("resume");
      }
    } finally {
      setLoading(false);
    }
  };

  // Info submitted → save then start analysis
  const handleUserInfo = async (info: UserInfoPayload) => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const handoff = getExtensionHandoff();
      const jdId = searchParams.get("jd_id") ?? handoff?.jd_id ?? undefined;
      const beforeInfo = await checkSession(sessionId);
      if (!beforeInfo.has_jd) {
        setBootstrapError(
          "This session has no job description saved. Go back to the Job Description step and paste or confirm the JD before continuing.",
        );
        return;
      }
      await saveUserInfo(sessionId, info, jdId);
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      sessionStorage.removeItem(APP_NAME_STORAGE_KEY);
      router.replace(`/session/${sessionId}?step=analysis`);
    } finally {
      setLoading(false);
    }
  };

  // JD 401 → re-auth and land back on this exact JD (AC7). A plain
  // router.push("/auth") would bounce right back here because proxy.ts's
  // AUTH_ONLY_PATHS branch treats any live NextAuth session as "signed in" —
  // sign out first so /auth actually renders the login form.
  function signInAgainForJd() {
    const dest = `/session/new${typeof window !== "undefined" ? window.location.search : ""}`;
    saveAuthReturnUrl(dest);
    void signOut({ callbackUrl: expiredSessionAuthUrl(dest) });
  }

  const stepIndex = STEPS.indexOf(step);

  function handleWizardBack() {
    if (stepIndex <= 0) {
      router.push("/dashboard");
      return;
    }
    goTo(STEPS[stepIndex - 1]!);
  }

  return (
    <div className="min-h-screen bg-sr-bg text-sr-fg">
      <div className="max-w-2xl mx-auto px-6 py-12">

        <button
          type="button"
          onClick={handleWizardBack}
          className="inline-flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-300 text-sm mb-8 transition-colors"
        >
          ← Back
        </button>

        {/* Progress bar */}
        <div className="flex items-center gap-2 mb-10">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2 flex-1">
              <button
                type="button"
                onClick={() => {
                  if (i < stepIndex) goTo(s);
                }}
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-colors ${
                  i < stepIndex
                    ? "bg-amber-400 text-slate-900 hover:bg-amber-300 cursor-pointer"
                    : i === stepIndex
                    ? "bg-amber-400 text-slate-900 ring-2 ring-amber-400/30"
                    : "bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 cursor-default"
                }`}
              >
                {i < stepIndex ? "✓" : i + 1}
              </button>
              <span
                className={`text-xs font-medium hidden sm:block ${
                  i === stepIndex
                    ? "text-slate-800 dark:text-slate-200"
                    : i < stepIndex
                    ? "text-slate-600 dark:text-slate-400"
                    : "text-slate-600 dark:text-slate-400"
                }`}
              >
                {STEP_LABELS[s]}
              </span>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-px ${i < stepIndex ? "bg-amber-400" : "bg-slate-200 dark:bg-slate-800"}`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8">

          {/*
           * Rendered outside every per-step / sessionId conditional below —
           * a failed JD fetch (e.g. the in-app jobs link at JobCard.tsx,
           * which carries no ?step= param) must be visible no matter which
           * step the URL's absence of ?step= happens to land on. Burying
           * this inside `step === "jd" && sessionId` was the reported bug:
           * a 404/network failure left the user on the resume step with no
           * message at all (defect #1 / I6).
           */}
          {jdLoadError && (
            <div
              className="mb-4 rounded-xl border border-red-400/30 bg-red-500/10 dark:bg-red-400/10 p-4 space-y-3"
              role="alert"
              data-testid="jd-load-error"
            >
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-700 dark:text-red-400 shrink-0 mt-0.5" />
                <p className="text-red-900 dark:text-red-100 text-sm leading-relaxed">
                  {jdLoadError.message}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-4 text-sm font-semibold">
                {jdLoadError.kind === "unauthorized" && (
                  <button
                    type="button"
                    onClick={signInAgainForJd}
                    className="text-red-800 dark:text-red-300 underline underline-offset-2"
                  >
                    Sign in again
                  </button>
                )}
                {(jdLoadError.kind === "network" || jdLoadError.kind === "server_error") && (
                  <button
                    type="button"
                    onClick={() => {
                      // Clear the stale message immediately so the retry
                      // shows a pending state instead of leaving the old
                      // error up with no indication anything is happening
                      // (S9).
                      setJdLoadError(null);
                      setJdRetryNonce((n) => n + 1);
                    }}
                    className="text-red-800 dark:text-red-300 underline underline-offset-2"
                  >
                    Try again
                  </button>
                )}
                <Link
                  href="/dashboard"
                  className="text-red-800 dark:text-red-300 underline underline-offset-2"
                >
                  Back to dashboard
                </Link>
              </div>
            </div>
          )}
          {!jdLoadError && jdLoadPending && (
            <div
              className="mb-4 flex items-center gap-2 text-slate-600 dark:text-slate-400 text-sm"
              data-testid="jd-load-pending"
            >
              <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-amber-400 border-t-transparent" />
              Loading your job description…
            </div>
          )}

          {/* ── Step 1: Upload Resume ───────────────────────────────────── */}
          {step === "resume" && !sessionId && (
            <div className="py-12 text-center">
              <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-amber-400 border-t-transparent" />
              <p className="text-slate-600 dark:text-slate-400 text-sm mt-4">
                {bootstrapError ?? "Starting your session…"}
              </p>
            </div>
          )}
          {step === "resume" && sessionId && (
            <div>
              <h1 className="text-xl font-bold mb-1">Name this application</h1>
              <p className="text-slate-600 dark:text-slate-400 text-sm mb-4">
                Pick a name you&apos;ll recognize on your dashboard — company and role work well.
                Your progress is saved under this name until you finish tailoring.
              </p>
              {applicationNameField}
              <h2 className="text-lg font-semibold mb-1">Upload your resume</h2>
              <p className="text-slate-600 dark:text-slate-400 text-sm mb-6">
                Upload a file, paste text, speak it, or reuse your saved master resume. Voice with
                live transcription is free in Chrome and Edge.
              </p>
              {!applicationName.trim() && (
                <p className="text-amber-800 dark:text-amber-200 text-sm mb-4 bg-amber-500/10 border border-amber-400/30 rounded-lg px-3 py-2">
                  Name this application above before continuing.
                </p>
              )}
              <ResumeUploader
                sessionId={sessionId}
                token={session?.backendAccessToken ?? undefined}
                onParsed={(parsed) => void handleResumeParsed(parsed)}
                hasMasterResume={hasMasterResume}
                onMasterResumeSaved={() => setHasMasterResume(true)}
                canProceed={applicationName.trim().length > 0}
              />
            </div>
          )}

          {/* ── Step 3: Job Description ─────────────────────────────────── */}
          {step === "jd" && !sessionId && (
            <div className="py-12 text-center">
              <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-amber-400 border-t-transparent" />
              <p className="text-slate-600 dark:text-slate-400 text-sm mt-4">
                {bootstrapError ?? "Starting your session…"}
              </p>
            </div>
          )}
          {step === "jd" && sessionId && (
            <div>
              <h1 className="text-xl font-bold mb-1">Job description</h1>
              {applicationName.trim() ? (
                <p className="text-slate-600 dark:text-slate-400 text-xs mb-2">
                  Application: <span className="font-medium text-slate-800 dark:text-slate-200">{applicationName}</span>
                </p>
              ) : (
                <>
                  <p className="text-slate-600 dark:text-slate-400 text-sm mb-4">
                    Name this application so you can find it on your dashboard.
                  </p>
                  {applicationNameField}
                </>
              )}
              <p className="text-slate-600 dark:text-slate-400 text-sm mb-6">
                Paste the full job posting. {PRODUCT_NAME} uses platform AI to extract ATS keywords
                and pre-fill your info from your resume.
              </p>
              <JDInput
                onSubmit={handleJD}
                loading={loading}
                initialJdText={jdText}
                jdId={searchParams.get("jd_id") ?? undefined}
                showCompletenessWarning={jdReviewRecommended}
                sourceUrl={jdSourceUrl}
                disabled={!applicationName.trim()}
                disabledHint="Name this application above before analyzing the job description."
              />
            </div>
          )}

          {/* ── Step 4: Your Info ───────────────────────────────────────── */}
          {step === "info" && !sessionId && (
            <div className="py-12 text-center">
              <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-amber-400 border-t-transparent" />
              <p className="text-slate-600 dark:text-slate-400 text-sm mt-4">
                {bootstrapError ?? "Starting your session…"}
              </p>
            </div>
          )}
          {step === "info" && sessionId && (
            <div>
              <h1 className="text-xl font-bold mb-1">Your information</h1>
              <p className="text-slate-600 dark:text-slate-400 text-sm mb-6">
                We pre-filled everything we found in your resume.
                Correct anything that looks wrong, then add your target role.
              </p>
              {infoHydrating && !parsedResume ? (
                <p className="text-slate-600 dark:text-slate-400 text-sm">Loading your resume details…</p>
              ) : (
                <UserInfoForm
                  onSubmit={handleUserInfo}
                  loading={loading}
                  parsedResume={parsedResume}
                  jdText={jdText}
                  jdTitle={jdTitle}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function NewSessionPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-sr-bg flex items-center justify-center text-slate-600 dark:text-slate-400">
          Loading…
        </div>
      }
    >
      <NewSessionContent />
    </Suspense>
  );
}
