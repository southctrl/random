"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"

interface UseUnsavedChangesOptions {
  initialHasChanges?: boolean
  onNavigateAway?: () => void
  confirmMessage?: string
}

interface UseUnsavedChangesReturn {
  hasUnsavedChanges: boolean
  setHasUnsavedChanges: (value: boolean) => void
  markDirty: () => void
  markClean: () => void
  showDialog: boolean
  setShowDialog: (value: boolean) => void
  pendingNavigation: string | null
  confirmNavigation: () => void
  cancelNavigation: () => void
}

export function useUnsavedChanges(
  options: UseUnsavedChangesOptions = {}
): UseUnsavedChangesReturn {
  const {
    initialHasChanges = false,
    confirmMessage = "You have unsaved changes. Are you sure you want to leave?",
  } = options

  const router = useRouter()
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(initialHasChanges)
  const [showDialog, setShowDialog] = useState(false)
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null)
  
  const hasUnsavedChangesRef = useRef(hasUnsavedChanges)
  useEffect(() => {
    hasUnsavedChangesRef.current = hasUnsavedChanges
  }, [hasUnsavedChanges])

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChangesRef.current) {
        e.preventDefault()
        return confirmMessage
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [confirmMessage])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      const link = target.closest("a")
      
      if (!link) return
      
      const href = link.getAttribute("href")
      if (!href || href.startsWith("http") || href.startsWith("//")) return
      
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

  const markDirty = useCallback(() => {
    setHasUnsavedChanges(true)
  }, [])

  const markClean = useCallback(() => {
    setHasUnsavedChanges(false)
  }, [])

  const confirmNavigation = useCallback(() => {
    setHasUnsavedChanges(false)
    setShowDialog(false)
    
    if (pendingNavigation) {
      router.push(pendingNavigation)
    }
    setPendingNavigation(null)
  }, [pendingNavigation, router])

  const cancelNavigation = useCallback(() => {
    setShowDialog(false)
    setPendingNavigation(null)
  }, [])

  return {
    hasUnsavedChanges,
    setHasUnsavedChanges,
    markDirty,
    markClean,
    showDialog,
    setShowDialog,
    pendingNavigation,
    confirmNavigation,
    cancelNavigation,
  }
}
