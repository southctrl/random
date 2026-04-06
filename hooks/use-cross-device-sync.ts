"use client"

import { useEffect, useCallback, useState } from "react"
import { useRouter } from "next/navigation"
import { useCloudSettings } from "./use-cloud-settings"
import { authClient } from "@/lib/auth-client"

interface CrossDeviceSyncReturn {
  isAuthenticated: boolean
  isLoading: boolean
  hasCloudToken: boolean
  hasLocalToken: boolean
  syncStatus: "synced" | "syncing" | "out-of-sync" | "no-token"
  syncFromCloud: () => Promise<boolean>
  syncToCloud: () => Promise<boolean>
  syncTokenToCloud: (token: string) => Promise<boolean>
  checkTokenValidity: () => Promise<boolean>
  user: { id: string; email?: string } | null
  cloudToken: string | null
}

export function useCrossDeviceSync(): CrossDeviceSyncReturn {
  const router = useRouter()
  const { 
    isLoading: settingsLoading, 
    saveDiscordToken, 
    getDiscordToken,
    validateToken,
    hasCloudToken,
    isTokenValid
  } = useCloudSettings()
  
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<{ id: string; email?: string } | null>(null)
  const [syncStatus, setSyncStatus] = useState<"synced" | "syncing" | "out-of-sync" | "no-token">("no-token")
  const [cloudToken, setCloudToken] = useState<string | null>(null)

  const hasLocalToken = typeof window !== "undefined" && !!localStorage.getItem("discord-token")

  useEffect(() => {
    const checkAuth = async () => {
      console.log("🔐 [CROSS-DEVICE SYNC] Checking authentication status...")
      const session = await authClient.getSession()
      
      setIsAuthenticated(!!session?.data?.user)
      setUser(session?.data?.user ? { id: session.data.user.id, email: session.data.user.email } : null)
      setIsLoading(false)
      
      console.log("👤 [CROSS-DEVICE SYNC] User authenticated:", !!session?.data?.user)
      console.log("💾 [CROSS-DEVICE SYNC] Has local token:", hasLocalToken)
    }

    checkAuth()
  }, [getDiscordToken])

  useEffect(() => {
    if (!isAuthenticated) {
      setSyncStatus("no-token")
    } else {
      setSyncStatus("no-token")
    }
  }, [isAuthenticated, hasCloudToken, isTokenValid])

  const syncFromCloudFn = useCallback(async (): Promise<boolean> => {
    console.log("🔄 [CLOUD SYNC] Starting sync from cloud...")
    
    if (!user?.id) {
      console.log("⏳ [CLOUD SYNC] User ID not ready, cannot sync from cloud")
      return false
    }
    
    setSyncStatus("syncing")
    
    try {
      const token = await getDiscordToken()
      
      if (token) {
        console.log("✅ [CLOUD SYNC] Retrieved token from cloud:", token.substring(0, 20) + "...")
        
        if (typeof window !== "undefined") {
          localStorage.removeItem("discord-token")
          console.log("🗑️ [CLOUD SYNC] Removed local token to avoid conflicts")
        }
        
        setCloudToken(token)
        setSyncStatus("synced")
        console.log("✅ [CLOUD SYNC] Sync from cloud completed successfully")
        return true
      }
      
      console.log("[CLOUD SYNC] No token found in cloud")
      setSyncStatus("no-token")
      return false
    } catch (err) {
      console.error("[CLOUD SYNC] Error syncing from cloud:", err)
      setSyncStatus("out-of-sync")
      return false
    }
  }, [getDiscordToken, user])

  useEffect(() => {
    if (isAuthenticated && hasCloudToken && user?.id) {
      console.log("🔄 [CROSS-DEVICE SYNC] User ID ready, triggering sync from cloud (NO LOCAL ONLY CLOUD)...")
      syncFromCloudFn()
    }
  }, [isAuthenticated, hasCloudToken, user?.id, syncFromCloudFn])
  
  const syncTokenToCloud = useCallback(async (token: string): Promise<boolean> => {
    console.log("[CLOUD SYNC] Starting sync to cloud...")
    console.log("📤 [CLOUD SYNC] Token to sync (first 20 chars):", token.substring(0, 20) + "...")
    setSyncStatus("syncing")
    
    try {
      const result = await saveDiscordToken(token)
      
      if (result.success) {
        console.log("✅ [CLOUD SYNC] Token successfully saved to cloud")
        setCloudToken(token)
        setSyncStatus("synced")
        console.log("✅ [CLOUD SYNC] Sync to cloud completed successfully")
        return true
      }
      
      console.log("[CLOUD SYNC] Failed to save token to cloud:", result.error)
      setSyncStatus("out-of-sync")
      return false
    } catch (err) {
      console.error("[CLOUD SYNC] Error syncing token to cloud:", err)
      setSyncStatus("out-of-sync")
      return false
    }
  }, [saveDiscordToken])

  const syncToCloud = useCallback(async (): Promise<boolean> => {
    console.log("[CLOUD SYNC] Starting auto-sync to cloud...")
    setSyncStatus("syncing")
    
    try {
      const localToken = typeof window !== "undefined" 
        ? localStorage.getItem("discord-token") 
        : null

      if (!localToken) {
        console.log("[CLOUD SYNC] No local token found to sync")
        setSyncStatus("no-token")
        return false
      }

      console.log("📤 [CLOUD SYNC] Local token found (first 20 chars):", localToken.substring(0, 20) + "...")

      const result = await saveDiscordToken(localToken)
      
      if (result.success) {
        console.log("✅ [CLOUD SYNC] Local token successfully saved to cloud")
        setSyncStatus("synced")
        return true
      }
      
      console.log("[CLOUD SYNC] Failed to save local token to cloud:", result.error)
      setSyncStatus("out-of-sync")
      return false
    } catch (err) {
      console.error("[CLOUD SYNC] Error auto-syncing to cloud:", err)
      setSyncStatus("out-of-sync")
      return false
    }
  }, [saveDiscordToken])

  const checkTokenValidity = useCallback(async (): Promise<boolean> => {
    console.log("🔍 [CROSS-DEVICE SYNC] Checking token validity...")
    const token = typeof window !== "undefined" 
      ? localStorage.getItem("discord-token") 
      : null

    if (!token) {
      console.log("[CROSS-DEVICE SYNC] No token found to validate")
      return false
    }

    console.log("🔑 [CROSS-DEVICE SYNC] Validating token (first 20 chars):", token.substring(0, 20) + "...")

    const result = await validateToken(token)
    
    if (!result.valid) {
      console.log("[CROSS-DEVICE SYNC] Token validation failed:", result.error)
      if (result.error?.includes("invalid") || result.error?.includes("expired")) {
        console.log("🚨 [CROSS-DEVICE SYNC] Token appears invalid/expired, redirecting to invalid token page")
        router.push("/invalid-token")
      }
      return false
    }

    console.log("✅ [CROSS-DEVICE SYNC] Token validation passed")
    return true
  }, [validateToken, router])

  return {
    isAuthenticated,
    isLoading: isLoading || settingsLoading,
    hasCloudToken,
    hasLocalToken,
    syncStatus,
    syncFromCloud: syncFromCloudFn,
    syncToCloud,
    syncTokenToCloud,
    checkTokenValidity,
    user,
    cloudToken,
  }
}
