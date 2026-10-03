"use client"

import { useState } from "react"
import { Check, Pencil, Trash2, X } from "lucide-react"
import type { ProfileBrick } from "@/lib/profile"
import { cn } from "@/lib/utils"

interface Props {
  brick: ProfileBrick
  onSave: (id: string, content: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

export function BrickCard({ brick, onSave, onDelete }: Props) {
  const [editing, setEditing] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [draft, setDraft] = useState(brick.content)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const longContent = brick.content.length > 180
  const displayContent =
    expanded || !longContent
      ? brick.content
      : `${brick.content.slice(0, 180).trimEnd()}…`

  async function save() {
    const trimmed = draft.trim()
    if (!trimmed) return
    setSaving(true)
    setError(null)
    try {
      await onSave(brick.id, trimmed)
      setEditing(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save brick.")
    } finally {
      setSaving(false)
    }
  }

  async function confirmAndDelete() {
    setDeleting(true)
    setError(null)
    try {
      await onDelete(brick.id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete brick.")
      setConfirmDelete(false)
    } finally {
      setDeleting(false)
    }
  }

  function cancelEdit() {
    setDraft(brick.content)
    setEditing(false)
    setError(null)
  }

  return (
    <article
      data-testid="brick-card"
      className="rounded-xl border border-slate-300 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 p-4 space-y-3"
    >
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
        {brick.source_doc_id ? (
          <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800">
            From upload
          </span>
        ) : null}
      </div>

      {editing ? (
        <textarea
          className="w-full min-h-[100px] rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
      ) : (
        <p className="text-sm text-slate-800 dark:text-slate-200 whitespace-pre-wrap break-words">
          {displayContent}
        </p>
      )}

      {longContent && !editing ? (
        <button
          type="button"
          className="text-xs text-amber-700 dark:text-amber-400 hover:underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      ) : null}

      {error ? <p className="text-xs text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="flex flex-wrap items-center gap-2">
        {editing ? (
          <>
            <button
              type="button"
              disabled={saving || !draft.trim()}
              onClick={() => void save()}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-semibold disabled:opacity-50"
            >
              <Check className="w-3.5 h-3.5" />
              Save
            </button>
            <button
              type="button"
              onClick={cancelEdit}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-xs"
            >
              <X className="w-3.5 h-3.5" />
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              data-testid="brick-edit"
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-xs"
            >
              <Pencil className="w-3.5 h-3.5" />
              Edit
            </button>
            {!confirmDelete ? (
              <button
                type="button"
                data-testid="brick-delete"
                onClick={() => setConfirmDelete(true)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-300 dark:border-red-800 text-red-700 dark:text-red-300 text-xs"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete
              </button>
            ) : (
              <button
                type="button"
                data-testid="brick-delete-confirm"
                disabled={deleting}
                onClick={() => void confirmAndDelete()}
                className={cn(
                  "inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold",
                  "bg-red-600 text-white disabled:opacity-50",
                )}
              >
                Confirm delete
              </button>
            )}
            {confirmDelete ? (
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                className="text-xs text-slate-600 dark:text-slate-400 hover:underline"
              >
                Cancel
              </button>
            ) : null}
          </>
        )}
      </div>
    </article>
  )
}
