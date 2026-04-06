"use client"

import { useState, useEffect, useCallback } from "react"
import useSWR from "swr"
import { authClient } from "@/lib/auth-client"
import { encryptToken, decryptToken } from "@/lib/encryption"

interface UserSettings {
  id: string
  user_id: string
  discord_token_encrypted: string | null
  discord_token_iv: string | null
  rpc_enabled: boolean
  rpc_type: string
  custom_rpc_settings: Record<string, unknown>
  game_rpc_settings: Record<string, unknown>
  app_settings: Record<string, unknown>
  token_is_valid: boolean
  token_last_validated_at: string | null
  last_device: string | null
  last_synced_at: string
  created_at: string
  updated_at: string
}

interface CloudSettingsReturn {
  settings: UserSettings | null
  isLoading: boolean
  isSyncing: boolean
  error: Error | null
  updateSettings: (updates: Partial<UserSettings>) => Promise<void>
  refreshSettings: () => Promise<void>
  saveDiscordToken: (token: string) => Promise<{ success: boolean; error?: string }>
  getDiscordToken: () => Promise<string | null>
  deleteDiscordToken: () => Promise<void>
  validateToken: (token: string) => Promise<{ valid: boolean; user?: unknown; error?: string }>
  isTokenValid: boolean
  hasCloudToken: boolean
}

const fetcher = async (url: string) => {
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch")
  return res.json()
}

export function useCloudSettings(): CloudSettingsReturn {
  const [userId, setUserId] = useState<string | null>(null)
  const [isSyncing, setIsSyncing] = useState(false)
  
  useEffect(() => {
    const getUser = async () => {
      const session = await authClient.getSession()
      setUserId(session?.data?.user?.id || null)
    }
    getUser()
  }, [])

  const { data, error, isLoading, mutate } = useSWR<{ settings: UserSettings }>(
    "/api/user/settings",
    fetcher,
    {
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 5000,
    }
  )

  const settings = data?.settings || null

  const updateSettings = useCallback(async (updates: Partial<UserSettings>) => {
    setIsSyncing(true)
    try {
      const response = await fetch("/api/user/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        console.error("Server response:", response.status, errorData)
        throw new Error(errorData.error || `Failed to update settings (${response.status})`)
      }

      await mutate()
    } catch (err) {
      console.error("Error updating settings:", err)
      throw err
    } finally {
      setIsSyncing(false)
    }
  }, [mutate])

  const refreshSettings = useCallback(async () => {
    await mutate()
  }, [mutate])

  const saveDiscordToken = useCallback(async (token: string): Promise<{ success: boolean; error?: string }> => {
    if (!userId) {
      console.log("[CLOUD SETTINGS] Cannot save token - no user ID")
      return { success: false, error: "Not authenticated" }
    }

    try {
      console.log("🔐 [CLOUD SETTINGS] Encrypting token for cloud storage...")
      const encrypted = await encryptToken(token, userId)

      console.log("📤 [CLOUD SETTINGS] Sending encrypted token to cloud...")
      const response = await fetch("/api/user/save-discord-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          encryptedToken: encrypted.ciphertext,
          iv: encrypted.iv,
          salt: encrypted.salt,
        }),
      })

      if (!response.ok) {
        const respData = await response.json()
        console.log("[CLOUD SETTINGS] Server rejected token:", respData.error)
        return { success: false, error: respData.error || "Failed to save token" }
      }

      console.log("[CLOUD SETTINGS] Token successfully saved to cloud database")
      if (typeof window !== "undefined") {
        localStorage.setItem("discord-token", token)
        console.log("[CLOUD SETTINGS] Token also saved to local storage")
      }

      await mutate()
      return { success: true }
    } catch (err) {
      console.error("[CLOUD SETTINGS] Error saving Discord token:", err)
      return { success: false, error: "Failed to encrypt and save token" }
    }
  }, [userId, mutate])

  const getDiscordToken = useCallback(async (): Promise<string | null> => {
    if (typeof window !== "undefined") {
      const localToken = localStorage.getItem("discord-token")
      if (localToken) {
        console.log("📱 [CLOUD SETTINGS] Found token in local storage (first 20 chars):", localToken.substring(0, 20) + "...")
        return localToken
      }
    }

    if (!userId) {
      console.log("⏳ [CLOUD SETTINGS] Cannot get cloud token - user ID not ready yet, retrying...")
      return null
    }

    try {
      console.log("📥 [CLOUD SETTINGS] Fetching token from cloud...")
      const response = await fetch("/api/user/save-discord-token")
      if (!response.ok) {
        console.log("[CLOUD SETTINGS] Failed to fetch token from cloud")
        return null
      }

      const respData = await response.json()
      if (!respData.hasToken || !respData.encryptedToken) {
        console.log("[CLOUD SETTINGS] No token found in cloud")
        return null
      }

      console.log("🔓 [CLOUD SETTINGS] Decrypting cloud token...")
      const decrypted = await decryptToken(
        {
          ciphertext: respData.encryptedToken,
          iv: respData.iv,
          salt: respData.salt,
        },
        userId
      )

      if (typeof window !== "undefined" && decrypted) {
        localStorage.setItem("discord-token", decrypted)
        console.log("[CLOUD SETTINGS] Decrypted token saved to local storage (first 20 chars):", decrypted.substring(0, 20) + "...")
      }

      console.log("[CLOUD SETTINGS] Token successfully retrieved from cloud")
      return decrypted
    } catch (err) {
      console.error("[CLOUD SETTINGS] Error getting Discord token:", err)
      return null
    }
  }, [userId])

  const deleteDiscordToken = useCallback(async () => {
    try {
      await fetch("/api/user/save-discord-token", { method: "DELETE" })
      
      if (typeof window !== "undefined") {
        localStorage.removeItem("discord-token")
      }

      await mutate()
    } catch (err) {
      console.error("Error deleting Discord token:", err)
    }
  }, [mutate])

  const validateToken = useCallback(async (token: string): Promise<{ valid: boolean; user?: unknown; error?: string }> => {
    console.log("🔍 [CLOUD SETTINGS] Starting token validation...")
    console.log("🔑 [CLOUD SETTINGS] Token to validate (first 20 chars):", token.substring(0, 20) + "...")
    
    try {
      const response = await fetch("/api/user/validate-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      })

      console.log("📡 [CLOUD SETTINGS] Validation response status:", response.status)
      const respData = await response.json()
      console.log("📊 [CLOUD SETTINGS] Validation response:", respData)
      
      if (respData.valid) {
        console.log("[CLOUD SETTINGS] Token validation successful")
        await mutate()
      } else {
        console.log("[CLOUD SETTINGS] Token validation failed:", respData.error)
      }

      return respData
    } catch (err) {
      console.error("[CLOUD SETTINGS] Error validating token:", err)
      return { valid: false, error: "Failed to validate token" }
    }
  }, [mutate])

  return {
    settings,
    isLoading,
    isSyncing,
    error: error || null,
    updateSettings,
    refreshSettings,
    saveDiscordToken,
    getDiscordToken,
    deleteDiscordToken,
    validateToken,
    isTokenValid: settings?.token_is_valid || false,
    hasCloudToken: !!settings?.discord_token_encrypted,
  }
}
