"use client"

import { useState, useCallback, useEffect } from "react"
import { useCloudSettings } from "./use-cloud-settings"
import { useCrossDeviceSync } from "./use-cross-device-sync"

export interface CloudSyncManager {
  isCloudFirst: boolean
  syncStatus: "synced" | "syncing" | "out-of-sync" | "no-token"
  syncToCloud: () => Promise<boolean>
  syncFromCloud: () => Promise<boolean>
  saveToCloud: (data: Record<string, any>) => Promise<boolean>
  isSyncing: boolean
  isLoading: boolean
}

export function useCloudSyncManager(): CloudSyncManager {
  const { updateSettings, isSyncing } = useCloudSettings()
  const { 
    isAuthenticated, 
    syncStatus, 
    syncToCloud: crossDeviceSyncToCloud, 
    syncFromCloud: crossDeviceSyncFromCloud,
    isLoading: crossDeviceLoading 
  } = useCrossDeviceSync()

  const [isCloudFirst, setIsCloudFirst] = useState(false)

  useEffect(() => {
    if (isAuthenticated && syncStatus === "synced") {
      setIsCloudFirst(true)
      console.log("[CLOUD SYNC MANAGER] Cloud-first mode enabled")
    }
  }, [isAuthenticated, syncStatus])

  const saveToCloud = useCallback(async (data: Record<string, any>): Promise<boolean> => {
    console.log("💾 [CLOUD SYNC MANAGER] Saving data to cloud...")
    console.log("📊 [CLOUD SYNC MANAGER] Data keys:", Object.keys(data))
    
    try {
      await updateSettings(data)
      console.log("✅ [CLOUD SYNC MANAGER] Data saved to cloud successfully")
      
      if (isCloudFirst) {
        console.log("🧹 [CLOUD SYNC MANAGER] Cloud-first mode - ensuring local consistency")
      }
      
      return true
    } catch (err) {
      console.error("[CLOUD SYNC MANAGER] Error saving to cloud:", err)
      return false
    }
  }, [updateSettings, isCloudFirst])

  const enhancedSyncToCloud = useCallback(async (): Promise<boolean> => {
    console.log("[CLOUD SYNC MANAGER] Starting enhanced sync to cloud...")
    
    const result = await crossDeviceSyncToCloud()
    
    if (result) {
      console.log("✅ [CLOUD SYNC MANAGER] Enhanced sync to cloud completed")
    } else {
      console.log("[CLOUD SYNC MANAGER] Enhanced sync to cloud failed")
    }
    
    return result
  }, [crossDeviceSyncToCloud])

  const enhancedSyncFromCloud = useCallback(async (): Promise<boolean> => {
    console.log("🔄 [CLOUD SYNC MANAGER] Starting enhanced sync from cloud...")
    
    const result = await crossDeviceSyncFromCloud()
    
    if (result) {
      console.log("✅ [CLOUD SYNC MANAGER] Enhanced sync from cloud completed")
      setIsCloudFirst(true)
    } else {
      console.log("[CLOUD SYNC MANAGER] Enhanced sync from cloud failed")
    }
    
    return result
  }, [crossDeviceSyncFromCloud])

  return {
    isCloudFirst,
    syncStatus,
    syncToCloud: enhancedSyncToCloud,
    syncFromCloud: enhancedSyncFromCloud,
    saveToCloud,
    isSyncing,
    isLoading: isSyncing || crossDeviceLoading || syncStatus === "syncing"
  }
}
