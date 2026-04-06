"use client"

import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

interface AutoSaveOptions<T> {
  initialData: T
  onSave: (data: T) => Promise<void>
  onCloudSync?: (data: T) => Promise<void>
  autoSaveDelay?: number
  requireExplicitSave?: boolean
  compareData?: (a: T, b: T) => boolean
}

interface AutoSaveReturn<T> {
  data: T
  setData: (data: T | ((prev: T) => T)) => void
  hasUnsavedChanges: boolean
  isSaving: boolean
  isSyncing: boolean
  saveError: string | null
  lastSynced: Date | null
  save: () => Promise<void>
  reset: () => void
  markSaved: () => void
  showDialog: boolean
  setShowDialog: (show: boolean) => void
  pendingNavigation: string | null
  confirmNavigation: () => void
  cancelNavigation: () => void
}

export function useAutoSave<T>(options: AutoSaveOptions<T>): AutoSaveReturn<T> {
  const {
    initialData,
    onSave,
    onCloudSync,
    autoSaveDelay = 0,
    requireExplicitSave = true,
    compareData = (a, b) => JSON.stringify(a) === JSON.stringify(b),
  } = options

  const memoizedCompareData = useMemo(() => compareData, [compareData])

  const router = useRouter()
  const [data, setDataInternal] = useState<T>(initialData)
  const [savedData, setSavedData] = useState<T>(initialData)
  const [isSaving, setIsSaving] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [lastSynced, setLastSynced] = useState<Date | null>(null)
  const [showDialog, setShowDialog] = useState(false)
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null)

  const hasUnsavedChanges = !memoizedCompareData(data, savedData)
  const hasUnsavedChangesRef = useRef(hasUnsavedChanges)
  const autoSaveTimerRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    hasUnsavedChangesRef.current = hasUnsavedChanges
  }, [hasUnsavedChanges])

  useEffect(() => {
    if (!hasUnsavedChanges && !memoizedCompareData(data, initialData)) {
      setDataInternal(initialData)
      setSavedData(initialData)
    }
  }, [initialData, hasUnsavedChanges, data, memoizedCompareData])

  const setData = useCallback((newData: T | ((prev: T) => T)) => {
    setDataInternal((prev) => {
      const resolved = typeof newData === "function" 
        ? (newData as (prev: T) => T)(prev) 
        : newData
      return resolved
    })
  }, [])

  const save = useCallback(async () => {
    if (!hasUnsavedChangesRef.current) return

    setIsSaving(true)
    setSaveError(null)

    try {
      await onSave(data)
      setSavedData(data)
      
      if (onCloudSync) {
        setIsSyncing(true)
        try {
          await onCloudSync(data)
          setLastSynced(new Date())
        } catch (err) {
          console.error("Cloud sync failed:", err)
        } finally {
          setIsSyncing(false)
        }
      }

      toast.success("Changes saved", {
        description: onCloudSync ? "Synced to cloud" : undefined,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save"
      setSaveError(message)
      toast.error("Failed to save", { description: message })
    } finally {
      setIsSaving(false)
    }
  }, [data, onSave, onCloudSync])

  useEffect(() => {
    if (autoSaveDelay > 0 && !requireExplicitSave && hasUnsavedChanges) {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
      }

      autoSaveTimerRef.current = setTimeout(() => {
        save()
      }, autoSaveDelay)

      return () => {
        if (autoSaveTimerRef.current) {
          clearTimeout(autoSaveTimerRef.current)
        }
      }
    }
  }, [autoSaveDelay, requireExplicitSave, hasUnsavedChanges, save])

  const reset = useCallback(() => {
    setDataInternal(initialData)
    setSavedData(initialData)
    setSaveError(null)
  }, [initialData])

  const markSaved = useCallback(() => {
    setSavedData(data)
  }, [data])

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChangesRef.current) {
        e.preventDefault()
        return "You have unsaved changes. Are you sure you want to leave?"
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      const link = target.closest("a")
      
      if (!link) return
      
      const href = link.getAttribute("href")
      if (!href || href.startsWith("http") || href.startsWith("//") || href.startsWith("#")) return
      
      if (hasUnsavedChangesRef.current) {
        e.preventDefault()
        e.stopPropagation()
        setPendingNavigation(href)
        setShowDialog(true)
      }
    }

    document.addEventListener("click", handleClick, true)
    return () => document.removeEventListener("click", handleClick, true)
  }, [])

  useEffect(() => {
    const handlePopState = () => {
      if (hasUnsavedChangesRef.current) {
        window.history.pushState(null, "", window.location.href)
        setShowDialog(true)
        setPendingNavigation(null)
      }
    }

    window.addEventListener("popstate", handlePopState)
    return () => window.removeEventListener("popstate", handlePopState)
  }, [])

  const confirmNavigation = useCallback(() => {
    setSavedData(data)
    setShowDialog(false)
    
    if (pendingNavigation) {
      router.push(pendingNavigation)
    } else {
      router.back()
    }
    setPendingNavigation(null)
  }, [data, pendingNavigation, router])

  const cancelNavigation = useCallback(() => {
    setShowDialog(false)
    setPendingNavigation(null)
  }, [])

  return {
    data,
    setData,
    hasUnsavedChanges,
    isSaving,
    isSyncing,
    saveError,
    lastSynced,
    save,
    reset,
    markSaved,
    showDialog,
    setShowDialog,
    pendingNavigation,
    confirmNavigation,
    cancelNavigation,
  }
}
