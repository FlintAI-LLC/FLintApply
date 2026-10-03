"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useSession } from "next-auth/react"
import { ArrowLeft, Loader2, Plus, XCircle } from "lucide-react"
import { useRequireAuth } from "@/lib/auth/guards"
import { liveBackendAccessToken } from "@/lib/auth/accessToken"
import { BrickCard } from "@/components/profile/BrickCard"
import {
  SECTION_LABELS,
  SECTION_ORDER,
  createProfileBrick,
  deleteProfileBrick,
  listProfileBricks,
  patchProfileBrick,
  type ProfileBrick,
} from "@/lib/profile"
import { clsx } from "clsx"

function BricksPageContent() {
  const { session, status } = useRequireAuth("/profile/bricks")
  const { data: clientSession } = useSession()
  const token = liveBackendAccessToken(clientSession ?? session)

  const [activeSection, setActiveSection] = useState<string>(SECTION_ORDER[0])
  const [bricks, setBricks] = useState<ProfileBrick[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [newContent, setNewContent] = useState("")
  const [savingNew, setSavingNew] = useState(false)

  const sectionTabs = useMemo(() => [...SECTION_ORDER], [])

  const loadBricks = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const rows = await listProfileBricks(token, activeSection)
      setBricks(rows)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load bricks")
      setBricks([])
    } finally {
      setLoading(false)
    }
  }, [token, activeSection])

  useEffect(() => {
    const t = window.setTimeout(() => {
      void loadBricks()
    }, 0)
    return () => window.clearTimeout(t)
  }, [loadBricks])

  async function handleSave(id: string, content: string) {
    if (!token) return
    const updated = await patchProfileBrick(token, id, content)
    setBricks((prev) => prev.map((b) => (b.id === id ? updated : b)))
  }

  async function handleDelete(id: string) {
    if (!token) return
    await deleteProfileBrick(token, id)
    setBricks((prev) => prev.filter((b) => b.id !== id))
  }

  async function saveNewBrick() {
    if (!token || !newContent.trim()) return
    setSavingNew(true)
    setError(null)
    try {
      const created = await createProfileBrick(token, activeSection, newContent.trim())
      setBricks((prev) => [...prev, created])
      setNewContent("")
      setAdding(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add brick")
    } finally {
      setSavingNew(false)
    }
  }

  if (status === "loading" || !session) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-slate-600 dark:text-slate-400" />
      </div>
    )
  }

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-6">
      <Link
        href="/profile"
        className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to profile
      </Link>

      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Resume bricks</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 max-w-2xl">
          Edit reusable bullets and paragraphs by section. Tailoring pulls from this library.
        </p>
      </header>

      {error ? (
        <div className="bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      ) : null}

      <div
        className="flex flex-wrap gap-2"
        role="tablist"
        aria-label="Resume sections"
        data-testid="brick-section-tabs"
      >
        {sectionTabs.map((section) => (
          <button
            key={section}
            type="button"
            role="tab"
            aria-selected={activeSection === section}
            data-testid={`brick-section-tab-${section}`}
            onClick={() => setActiveSection(section)}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors",
              activeSection === section
                ? "bg-amber-600 text-white border-amber-600"
                : "bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200",
            )}
          >
            {SECTION_LABELS[section] ?? section}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3" data-testid="brick-list-skeleton">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-24 rounded-xl bg-slate-200/80 dark:bg-slate-800/80 animate-pulse"
            />
          ))}
        </div>
      ) : bricks.length === 0 && !adding ? (
        <p
          data-testid="brick-empty-state"
          className="text-sm text-slate-600 dark:text-slate-400 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl px-4 py-8 text-center"
        >
          No bricks in this section. Add one or upload a resume.
        </p>
      ) : (
        <div className="space-y-4">
          {bricks.map((brick) => (
            <BrickCard
              key={brick.id}
              brick={brick}
              onSave={handleSave}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {adding ? (
        <div
          data-testid="brick-add-form"
          className="rounded-xl border border-slate-300 dark:border-slate-700 p-4 space-y-3"
        >
          <textarea
            className="w-full min-h-[120px] rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="Brick content…"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={savingNew || !newContent.trim()}
              onClick={() => void saveNewBrick()}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                setAdding(false)
                setNewContent("")
              }}
              className="px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-xs"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm font-semibold"
        >
          <Plus className="w-4 h-4" />
          Add brick
        </button>
      )}
    </main>
  )
}

export default function ProfileBricksPage() {
  return <BricksPageContent />
}
