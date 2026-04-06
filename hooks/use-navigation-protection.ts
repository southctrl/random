"use client"

import { useEffect, useCallback, useState } from "react"
import { useRouter } from "next/navigation"

interface UseNavigationProtectionOptions {
    hasUnsavedChanges: boolean
    onConfirmNavigation?: () => void
    onCancelNavigation?: () => void
}

export function useNavigationProtection({
    hasUnsavedChanges,
    onConfirmNavigation,
    onCancelNavigation,
}: UseNavigationProtectionOptions) {
    const router = useRouter()
    const [showDialog, setShowDialog] = useState(false)
    const [pendingUrl, setPendingUrl] = useState<string | null>(null)

    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (hasUnsavedChanges) {
                console.log(" [NAV] Preventing browser close/refresh")
                e.preventDefault()
                e.returnValue = ""
                return ""
            }
        }

        window.addEventListener("beforeunload", handleBeforeUnload)
        
        return () => {
            window.removeEventListener("beforeunload", handleBeforeUnload)
        }
    }, [hasUnsavedChanges])

    useEffect(() => {
        const handleLinkClick = (e: MouseEvent) => {
            if (!hasUnsavedChanges) return

            console.log(" [NAV] Click detected, checking for navigation...")
            
            const target = e.target as HTMLElement
            const link = target.closest('a')
            
            if (link && link.href) {
                console.log(" [NAV] Link clicked:", link.href)
                e.preventDefault()
                e.stopPropagation()
                
                setPendingUrl(link.href)
                setShowDialog(true)
            }
        }

        const handlePopState = (e: PopStateEvent) => {
            if (hasUnsavedChanges) {
                console.log(" [NAV] Popstate detected (back/forward button)")
                e.preventDefault()
                setShowDialog(true)
                setPendingUrl(window.location.href)
            }
        }

        document.addEventListener('click', handleLinkClick, true)
        window.addEventListener('popstate', handlePopState)
        
        return () => {
            document.removeEventListener('click', handleLinkClick, true)
            window.removeEventListener('popstate', handlePopState)
        }
    }, [hasUnsavedChanges])

    const handleConfirm = useCallback(() => {
        console.log(" [NAV] Navigation confirmed")
        setShowDialog(false)
        
        if (pendingUrl) {
            console.log(" [NAV] Navigating to:", pendingUrl)
            window.location.href = pendingUrl
            setPendingUrl(null)
        }
        
        onConfirmNavigation?.()
    }, [pendingUrl, onConfirmNavigation])

    const handleCancel = useCallback(() => {
        console.log(" [NAV] Navigation cancelled")
        setShowDialog(false)
        setPendingUrl(null)
        onCancelNavigation?.()
    }, [onCancelNavigation])

    const navigateWithProtection = useCallback((url: string) => {
        if (hasUnsavedChanges) {
            setPendingUrl(url)
            setShowDialog(true)
            return false
        } else {
            router.push(url)
            return true
        }
    }, [hasUnsavedChanges, router])

    return {
        navigateWithProtection,
        showDialog,
        onConfirm: handleConfirm,
        onCancel: handleCancel,
    }
}
