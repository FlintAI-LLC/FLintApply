"use client"

import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { LegalPageShell } from "@/components/legal/LegalPageShell"
import { PRIVACY_EMAIL } from "@/lib/brand"

const TOPIC_QUERY_VALUES = new Set([
  "data_subject_request",
  "sub_processor_objection",
  "security_disclosure",
  "ccpa_inquiry",
  "bug_report",
  "product_feedback",
  "other",
])

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const LAST_UPDATED = "2026-05-31"

type ContactStatus =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success" }
  | { kind: "error"; message: string }

export default function DpoContactPage() {
  return (
    <Suspense fallback={<ContactPageFallback />}>
      <DpoContactForm />
    </Suspense>
  )
}

function ContactPageFallback() {
  return (
    <LegalPageShell title="Contact us" lastUpdated={LAST_UPDATED}>
      <p className="text-slate-600 dark:text-slate-400">Loading form…</p>
    </LegalPageShell>
  )
}

function DpoContactForm() {
  const searchParams = useSearchParams()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [topic, setTopic] = useState("data_subject_request")
  const [message, setMessage] = useState("")
  const [status, setStatus] = useState<ContactStatus>({ kind: "idle" })

  useEffect(() => {
    const fromQuery = searchParams.get("topic")
    if (fromQuery && TOPIC_QUERY_VALUES.has(fromQuery)) {
      setTopic(fromQuery)
    }
  }, [searchParams])

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setStatus({ kind: "submitting" })
    try {
      const res = await fetch(`${API_BASE}/api/legal/dpo-contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, topic, message }),
      })
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          detail?: string
        }
        throw new Error(body.detail ?? `Request failed (${res.status})`)
      }
      setStatus({ kind: "success" })
      setName("")
      setEmail("")
      setTopic("data_subject_request")
      setMessage("")
    } catch (err) {
      setStatus({
        kind: "error",
        message:
          err instanceof Error ? err.message : "Unable to send the message.",
      })
    }
  }

  const submitting = status.kind === "submitting"

  return (
    <LegalPageShell title="Contact us" lastUpdated={LAST_UPDATED}>
      <p>
        Submissions are delivered to{" "}
        <a href={`mailto:${PRIVACY_EMAIL}`}>{PRIVACY_EMAIL}</a>{" "}
        via Resend. Use <strong>Report a bug</strong> or <strong>Product feedback</strong> for
        app issues; privacy and GDPR topics are listed below as well.
      </p>

      <form
        onSubmit={onSubmit}
        className="not-prose mt-6 space-y-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/60 p-6"
      >
        <div className="space-y-2">
          <label
            htmlFor="dpo-name"
            className="block text-xs font-medium uppercase tracking-widest text-slate-600 dark:text-slate-400"
          >
            Your name
          </label>
          <input
            id="dpo-name"
            name="name"
            required
            maxLength={120}
            disabled={submitting}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-amber-400 focus:outline-none"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="dpo-email"
            className="block text-xs font-medium uppercase tracking-widest text-slate-600 dark:text-slate-400"
          >
            Reply-to email
          </label>
          <input
            id="dpo-email"
            type="email"
            name="email"
            required
            maxLength={254}
            disabled={submitting}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-amber-400 focus:outline-none"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="dpo-topic"
            className="block text-xs font-medium uppercase tracking-widest text-slate-600 dark:text-slate-400"
          >
            Topic
          </label>
          <select
            id="dpo-topic"
            name="topic"
            required
            disabled={submitting}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-amber-400 focus:outline-none"
          >
            <option value="bug_report">Report a bug</option>
            <option value="product_feedback">Product feedback</option>
            <option value="data_subject_request">
              Data subject request (access / erasure / portability)
            </option>
            <option value="sub_processor_objection">
              Sub-processor change objection
            </option>
            <option value="security_disclosure">Security disclosure</option>
            <option value="ccpa_inquiry">CCPA inquiry</option>
            <option value="other">Other privacy concern</option>
          </select>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="dpo-message"
            className="block text-xs font-medium uppercase tracking-widest text-slate-600 dark:text-slate-400"
          >
            Message
          </label>
          <textarea
            id="dpo-message"
            name="message"
            required
            minLength={20}
            maxLength={4000}
            disabled={submitting}
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-amber-400 focus:outline-none"
          />
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Please describe your request.  Minimum 20 characters.
          </p>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-amber-500 px-5 py-2 text-sm font-semibold text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Sending…" : "Send message"}
        </button>

        {status.kind === "success" ? (
          <p
            role="status"
            className="rounded-md border border-emerald-200 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/40 px-3 py-2 text-sm text-emerald-800 dark:text-emerald-200"
          >
            Thanks — your message has been sent.  We respond within 30 days
            (most requests within 5 business days).
          </p>
        ) : null}

        {status.kind === "error" ? (
          <p
            role="alert"
            className="rounded-md border border-rose-200 dark:border-rose-700 bg-rose-50 dark:bg-rose-900/40 px-3 py-2 text-sm text-rose-800 dark:text-rose-200"
          >
            {status.message}
          </p>
        ) : null}
      </form>
    </LegalPageShell>
  )
}
