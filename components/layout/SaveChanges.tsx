"use client"

import { Button } from "@/components/ui/button"
import { Check, Loader2, Cloud, CloudOff, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface SaveChangesProps {
  show: boolean
  saving: boolean
  disabled?: boolean
  onSave: () => void
  isSyncing?: boolean
  syncError?: string | null
  lastSynced?: Date | null
  position?: "bottom" | "floating"
}

export function SaveChanges({
  show,
  saving,
  disabled,
  onSave,
  isSyncing = false,
  syncError = null,
  lastSynced = null,
  position = "bottom",
}: SaveChangesProps) {
  if (!show) return null

  const formatLastSynced = (date: Date | null) => {
    if (!date) return null
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    
    if (minutes < 1) return "Just now"
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div
      className={cn(
        "rounded-2xl border border-white/10 bg-black/35 p-3 backdrop-blur-xl",
        position === "floating" && "fixed bottom-4 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 shadow-2xl md:bottom-6",
        position === "bottom" && "mt-6"
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium text-white">
              Save changes
            </p>
            {syncError ? (
              <span className="flex items-center gap-1 text-xs text-red-400">
                <AlertCircle className="h-3 w-3" />
                Sync failed
              </span>
            ) : isSyncing ? (
              <span className="flex items-center gap-1 text-xs text-sky-400">
                <Cloud className="h-3 w-3 animate-pulse" />
                Syncing...
              </span>
            ) : lastSynced ? (
              <span className="flex items-center gap-1 text-xs text-green-400">
                <Cloud className="h-3 w-3" />
                {formatLastSynced(lastSynced)}
              </span>
            ) : null}
          </div>
          <p className="truncate text-xs text-white/50">
            You have unsaved edits
          </p>
        </div>
        <Button
          type="button"
          onClick={onSave}
          disabled={disabled || saving}
          className="shrink-0 rounded-full bg-[#47a6ff] text-white hover:bg-[#6bb8ff] disabled:opacity-50"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check className="mr-2 h-4 w-4" />
              Save
            </>
          )}
        </Button>
      </div>
    </div>
  )
}

export function FloatingSaveButton({
  show,
  saving,
  disabled,
  onSave,
  hasUnsavedChanges,
}: {
  show: boolean
  saving: boolean
  disabled?: boolean
  onSave: () => void
  hasUnsavedChanges: boolean
}) {
  if (!show || !hasUnsavedChanges) return null

  return (
    <div className="fixed bottom-20 right-4 z-50 md:bottom-6 md:right-6">
      <Button
        type="button"
        onClick={onSave}
        disabled={disabled || saving}
        className="h-14 w-14 rounded-full bg-[#47a6ff] p-0 shadow-lg shadow-sky-500/25 hover:bg-[#6bb8ff] disabled:opacity-50 md:h-12 md:w-auto md:px-6"
      >
        {saving ? (
          <Loader2 className="h-6 w-6 animate-spin md:h-4 md:w-4" />
        ) : (
          <>
            <Check className="h-6 w-6 md:mr-2 md:h-4 md:w-4" />
            <span className="hidden md:inline">Save Changes</span>
          </>
        )}
      </Button>
    </div>
  )
}
