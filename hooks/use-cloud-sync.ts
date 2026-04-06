"use client"

import { useState, useEffect, useCallback, useRef } from 'react'
import { cloudSync, PresenceData, SyncResponse, ConflictResponse } from '@/lib/sync-service'

interface UseCloudSyncOptions {
  autoSync?: boolean
  syncInterval?: number
  onSyncUpdate?: (data: SyncResponse) => void
  onConflict?: (conflict: ConflictResponse) => Promise<void>
}

interface UseCloudSyncReturn {
  data: PresenceData
  loading: boolean
  error: string | null
  lastSyncTime: string | null
  deviceId: string
  isCurrentDevice: boolean
  syncInProgress: boolean
  saveSettings: (data: PresenceData, force?: boolean) => Promise<boolean>
  forceSync: () => Promise<void>
  resolveConflict: (choice: 'server' | 'client') => Promise<void>
  refresh: () => Promise<void>
}

export function useCloudSync(options: UseCloudSyncOptions = {}): UseCloudSyncReturn {
  const { autoSync = true, syncInterval = 30000, onSyncUpdate, onConflict } = options
  
  const [data, setData] = useState<PresenceData>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null)
  const [deviceId] = useState(() => cloudSync.getDeviceId())
  const [isCurrentDevice, setIsCurrentDevice] = useState(true)
  const [syncInProgress, setSyncInProgress] = useState(false)
  
  const conflictDataRef = useRef<ConflictResponse | null>(null)

  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await cloudSync.fetchPresenceSettings()
      setData({
        rich: response.rich,
        custom: response.custom,
        spotify: response.spotify,
      })
      setLastSyncTime(response.lastSyncedAt)
      setIsCurrentDevice(response.currentDevice === deviceId)
      
      if (onSyncUpdate) {
        onSyncUpdate(response)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }, [deviceId, onSyncUpdate])

  const saveSettings = useCallback(async (settings: PresenceData, force = false): Promise<boolean> => {
    try {
      setSyncInProgress(true)
      setError(null)
      
      const result = await cloudSync.savePresenceSettings(settings, force)
      
      if (result.success) {
        await refresh()
        return true
      } else if (result.conflict) {
        conflictDataRef.current = result.conflict
        setError(result.conflict.message)
        
        if (onConflict) {
          await onConflict(result.conflict)
        } else {
          await handleConflict(result.conflict)
        }
        return false
      }
      
      return false
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save data')
      return false
    } finally {
      setSyncInProgress(false)
    }
  }, [refresh, onConflict])

  const handleConflict = useCallback(async (conflict: ConflictResponse) => {
    const choice = window.confirm(
      `Settings were updated on another device (${conflict.lastDevice}).\n\n` +
      `Click OK to use the server version, or Cancel to keep your changes.`
    )
    
    if (choice) {
      await resolveConflict('server')
    } else {
      await resolveConflict('client')
    }
  }, [])

  const resolveConflict = useCallback(async (choice: 'server' | 'client') => {
    if (!conflictDataRef.current) return

    try {
      if (choice === 'server') {
        const serverState = await cloudSync.getServerState()
        setData(serverState.serverState)
        setLastSyncTime(serverState.lastSyncedAt)
        
        await cloudSync.forceSync(deviceId)
        await refresh()
      } else {
        await saveSettings(data, true)
      }
      
      await cloudSync.markConflictResolved()
      conflictDataRef.current = null
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve conflict')
    }
  }, [data, deviceId, saveSettings, refresh])

  const forceSync = useCallback(async () => {
    try {
      setSyncInProgress(true)
      setError(null)
      
      await cloudSync.forceSync(deviceId)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to force sync')
    } finally {
      setSyncInProgress(false)
    }
  }, [deviceId, refresh])

  useEffect(() => {
    refresh()
    
    if (autoSync) {
      cloudSync.startAutoSync(syncInterval)
    }

    const handleSyncUpdate = (event: CustomEvent<SyncResponse>) => {
      const updateData = event.detail
      setData({
        rich: updateData.rich,
        custom: updateData.custom,
        spotify: updateData.spotify,
      })
      setLastSyncTime(updateData.lastSyncedAt)
      setIsCurrentDevice(updateData.currentDevice === deviceId)
      
      if (onSyncUpdate) {
        onSyncUpdate(updateData)
      }
    }

    window.addEventListener('presence-sync-update', handleSyncUpdate as EventListener)
    
    return () => {
      cloudSync.stopAutoSync()
      window.removeEventListener('presence-sync-update', handleSyncUpdate as EventListener)
    }
  }, [refresh, autoSync, syncInterval, deviceId, onSyncUpdate])

  return {
    data,
    loading,
    error,
    lastSyncTime,
    deviceId,
    isCurrentDevice,
    syncInProgress,
    saveSettings,
    forceSync,
    resolveConflict,
    refresh,
  }
}
