"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { AlertCircle, CheckCircle2, FileText, Upload } from "lucide-react"
import { cn } from "@/lib/utils"
import { StoryRecorder } from "@/components/profile/StoryRecorder"
import { MasterResumeReplaceDialog } from "@/components/profile/MasterResumeReplaceDialog"
import { hasMeaningfulStoryDraft, loadStoryDraft } from "@/lib/storyDraft"
import {
  MASTER_CHUNK_RICH_THRESHOLD,
  MAX_MASTER_SOURCE_UPLOADS,
} from "@/lib/profile"

interface Props {
  onSubmit: (payload: { file?: File; text?: string }) => Promise<void>
  token: string
  loading: boolean
  compact?: boolean
  /** Live chunks already on profile — upload/paste replaces them entirely. */
  existingChunkCount?: number
  /** Distinct merge uploads (POST /resume), max {MAX_MASTER_SOURCE_UPLOADS}. */
  sourceUploadCount?: number
  defaultStory?: boolean
  onStoryComplete?: () => void
}

type Mode = "story" | "upload" | "paste"

const TABS: { id: Mode; label: string }[] = [
  { id: "story",  label: "🎙 Tell your story" },
  { id: "upload", label: "Upload file" },
  { id: "paste",  label: "Paste text" },
]

export function ProfileUploadZone({
  onSubmit,
  token,
  loading,
  compact = false,
  existingChunkCount = 0,
  sourceUploadCount = 0,
  defaultStory = false,
  onStoryComplete,
}: Props) {
  const [mode, setMode]       = useState<Mode>(defaultStory ? "story" : "upload")
  const [dragging, setDragging] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [pasteText, setPasteText] = useState("")
  const [replaceDialogOpen, setReplaceDialogOpen] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [pendingReplace, setPendingReplace] = useState<
    { kind: "file"; file: File } | { kind: "paste" } | null
  >(null)

  const hasExistingMaster = existingChunkCount > 0
  const atSourceUploadLimit = sourceUploadCount >= MAX_MASTER_SOURCE_UPLOADS
  const profileIsRich = existingChunkCount >= MASTER_CHUNK_RICH_THRESHOLD

  const finishSubmit = useCallback(() => {
    setPasteText("")
    setSuccessMessage(
      existingChunkCount > 0
        ? "New content merged into your master resume. Check the chunk list below for updates."
        : "Master resume saved. Your chunks below are updated.",
    )
    if (fileInputRef.current) fileInputRef.current.value = ""
  }, [existingChunkCount])

  const runReplace = useCallback(
    async (payload: { file?: File; text?: string }) => {
      if (submitting || loading) return
      setSubmitting(true)
      setReplaceDialogOpen(false)
      setPendingReplace(null)
      setSuccessMessage(null)
      setError(null)
      try {
        await onSubmit(payload)
        finishSubmit()
      } catch (e) {
        throw e
      } finally {
        setSubmitting(false)
      }
    },
    [onSubmit, loading, finishSubmit, submitting],
  )

  const requestReplace = useCallback(
    (next: { kind: "file"; file: File } | { kind: "paste" }) => {
      if (loading || submitting) return
      if (atSourceUploadLimit) {
        setError(
          `You have reached the limit of ${MAX_MASTER_SOURCE_UPLOADS} merged file/paste uploads. Edit chunks below, or save a new draft from Tell your story to replace everything.`,
        )
        return
      }
      setSuccessMessage(null)
      if (!hasExistingMaster) {
        if (next.kind === "file") void runReplace({ file: next.file })
        else void runReplace({ text: pasteText })
        return
      }
      setPendingReplace(next)
      setReplaceDialogOpen(true)
    },
    [atSourceUploadLimit, hasExistingMaster, runReplace, pasteText, loading, submitting],
  )

  useEffect(() => {
    if (defaultStory) return
    if (hasMeaningfulStoryDraft(loadStoryDraft())) {
      setMode("story")
    }
  }, [defaultStory])

  const handleFile = useCallback(
    async (file: File) => {
      setError(null)
      if (file.size > 5 * 1024 * 1024) { setError("File exceeds 5MB limit."); return }
      const allowed = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
      ]
      if (!allowed.includes(file.type)) { setError("Only PDF, DOCX, and TXT files are supported."); return }
      requestReplace({ kind: "file", file })
    },
    [requestReplace],
  )

  const handlePaste = async () => {
    if (!pasteText.trim() || loading || submitting) return
    setError(null)
    setSuccessMessage(null)
    if (!hasExistingMaster) {
      setSubmitting(true)
      try {
        await onSubmit({ text: pasteText })
        finishSubmit()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to process resume text.")
      } finally {
        setSubmitting(false)
      }
      return
    }
    requestReplace({ kind: "paste" })
  }

  const confirmReplace = () => {
    if (!pendingReplace || loading || submitting) return
    if (pendingReplace.kind === "file") {
      void runReplace({ file: pendingReplace.file }).catch((e) => {
        setError(e instanceof Error ? e.message : "Upload failed.")
      })
    } else {
      void runReplace({ text: pasteText }).catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to process resume text.")
      })
    }
  }

  return (
    <div className={cn("space-y-4 relative", compact && "space-y-3")}>
      {!compact && (
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Master resume</h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Tell your story, upload a file, or paste text — we'll chunk and embed it automatically.
          </p>
        </div>
      )}

      {/* Mode tabs */}
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => { setMode(tab.id); setError(null) }}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5",
              mode === tab.id
                ? "bg-amber-400 text-slate-900"
                : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {hasExistingMaster && atSourceUploadLimit && (
        <div className="rounded-xl border border-amber-500/35 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-950 dark:text-amber-100">
          <strong>{existingChunkCount}</strong> chunks indexed ·{" "}
          <strong>{sourceUploadCount}/{MAX_MASTER_SOURCE_UPLOADS}</strong> merge uploads used. You cannot add
          another file or paste merge — edit chunks below, or use <strong>Tell your story</strong> to replace the
          full master resume.
        </div>
      )}
      {hasExistingMaster && !atSourceUploadLimit && profileIsRich && (
        <div className="rounded-xl border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-900/50 px-4 py-3 text-sm text-slate-800 dark:text-slate-200">
          <strong>{existingChunkCount}</strong> chunks indexed — your profile is already detailed. Add another
          upload only if something is missing ({sourceUploadCount}/{MAX_MASTER_SOURCE_UPLOADS} merges used).
          Otherwise edit chunks below. <strong>Tell your story → Save</strong> still replaces everything.
        </div>
      )}
      {hasExistingMaster && !atSourceUploadLimit && !profileIsRich && (
        <div className="rounded-xl border border-emerald-500/35 bg-emerald-50 dark:bg-emerald-950/30 px-4 py-3 text-sm text-emerald-950 dark:text-emerald-100">
          <strong>{existingChunkCount}</strong> chunk{existingChunkCount === 1 ? "" : "s"} indexed (
          {sourceUploadCount}/{MAX_MASTER_SOURCE_UPLOADS} merges). Use <strong>Upload file</strong> or{" "}
          <strong>Paste text</strong> to add more (deduped). <strong>Tell your story → Save</strong> replaces the
          whole master resume.
        </div>
      )}

      {/* Story */}
      {mode === "story" && (
        <StoryRecorder
          token={token}
          onSaved={() => {
            onStoryComplete?.()
          }}
        />
      )}

      {/* Upload */}
      {mode === "upload" && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) void handleFile(f) }}
          className={cn(
            "border-2 border-dashed rounded-xl text-center cursor-pointer transition-colors",
            compact ? "p-6" : "p-10",
            dragging ? "border-amber-400 bg-amber-500/5 dark:bg-amber-400/5" : "border-slate-300 dark:border-slate-700 hover:border-slate-500",
            loading && "pointer-events-none opacity-60",
          )}
          onClick={() => document.getElementById("profile-file-input")?.click()}
        >
          <Upload className={cn("text-slate-600 dark:text-slate-400 mx-auto mb-2", compact ? "w-8 h-8" : "w-10 h-10")} />
          <p className="text-slate-700 dark:text-slate-300 font-medium">Drop your resume here</p>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">PDF, DOCX, or TXT · Max 5MB</p>
          <input
            ref={fileInputRef}
            id="profile-file-input"
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void handleFile(f) }}
          />
        </div>
      )}

      {/* Paste */}
      {mode === "paste" && (
        <div className="space-y-3">
          <textarea
            value={pasteText}
            onChange={(e) => {
              setPasteText(e.target.value)
              if (successMessage) setSuccessMessage(null)
            }}
            placeholder="Paste your master resume text here…"
            disabled={loading}
            className="w-full h-48 bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-4 text-slate-800 dark:text-slate-200 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400 placeholder-slate-600 disabled:opacity-60"
          />
          <div className="flex items-center justify-between">
            <span className="text-slate-600 dark:text-slate-400 text-xs">{pasteText.length.toLocaleString()} characters</span>
            <button
              type="button"
              onClick={() => void handlePaste()}
              disabled={!pasteText.trim() || loading || submitting}
              className="px-5 py-2 bg-amber-400 text-slate-900 font-semibold rounded-lg hover:bg-amber-300 disabled:opacity-40 transition-colors text-sm"
            >
              {loading
                ? "Processing…"
                : hasExistingMaster
                  ? "Add to master resume…"
                  : "Save master resume"}
            </button>
          </div>
        </div>
      )}

      {/* Global loading overlay */}
      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-slate-50/75 dark:bg-slate-950/75">
          <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 text-sm px-4 py-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white/90 dark:bg-slate-900/90">
            <div className="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
            Chunking and embedding your resume…
          </div>
        </div>
      )}

      {successMessage && (
        <div className="flex items-start gap-2 text-emerald-800 dark:text-emerald-300 text-sm bg-emerald-500/10 border border-emerald-500/25 rounded-lg p-3">
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          {successMessage}
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 text-red-700 dark:text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg p-3">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {compact && mode === "upload" && hasExistingMaster && (
        <p className="text-xs text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5" />
          Uploads merge into your existing chunks (duplicates skipped).
        </p>
      )}

      <MasterResumeReplaceDialog
        open={replaceDialogOpen}
        busy={loading || submitting}
        actionLabel={pendingReplace?.kind === "paste" ? "Pasting new text" : "Uploading a file"}
        chunkCount={existingChunkCount}
        onClose={() => {
          setReplaceDialogOpen(false)
          setPendingReplace(null)
        }}
        onConfirm={confirmReplace}
      />
    </div>
  )
}
