interface PresenceData {
  rich?: any
  custom?: any
  spotify?: any
}

interface SyncResponse {
  rich: any
  custom: any
  spotify: any
  lastDevice: string | null
  lastSyncedAt: string | null
  needsSync: boolean
  currentDevice: string
}

interface ConflictResponse {
  error: "sync_conflict"
  message: string
  lastDevice: string
  serverTime: string
  needsRefresh: boolean
}

class CloudSyncService {
  private deviceId: string
  private lastSyncTime: string | null = null
  private syncInProgress = false
  private syncInterval: NodeJS.Timeout | null = null
  private pendingChanges: PresenceData = {}
  private conflictCallback: ((conflict: ConflictResponse) => Promise<void>) | null = null

  constructor() {
    this.deviceId = this.generateDeviceId()
    this.loadLastSyncTime()
  }

  private generateDeviceId(): string {
    if (typeof window === 'undefined') return 'server'
    
    const userAgent = navigator.userAgent
    const fingerprint = `${userAgent}-${screen.width}x${screen.height}-${new Date().getTimezoneOffset()}`
    return btoa(fingerprint).replace(/[^a-zA-Z0-9]/g, '').toLowerCase().slice(0, 32)
  }

  private loadLastSyncTime() {
    if (typeof window === 'undefined') return
    this.lastSyncTime = localStorage.getItem('presence_last_sync')
  }

  private saveLastSyncTime(time: string) {
    if (typeof window === 'undefined') return
    localStorage.setItem('presence_last_sync', time)
    this.lastSyncTime = time
  }

  async fetchPresenceSettings(): Promise<SyncResponse> {
    const params = new URLSearchParams()
    if (this.lastSyncTime) {
      params.append('lastSync', this.lastSyncTime)
    }

    const response = await fetch(`/api/presence-settings?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch settings: ${response.statusText}`)
    }

    const data: SyncResponse = await response.json()
    
    if (data.needsSync && data.lastSyncedAt) {
      this.saveLastSyncTime(data.lastSyncedAt)
    }

    return data
  }

  async savePresenceSettings(data: PresenceData, force = false): Promise<{ success: boolean; conflict?: ConflictResponse }> {
    if (this.syncInProgress && !force) {
      this.pendingChanges = { ...this.pendingChanges, ...data }
      return { success: true }
    }

    this.syncInProgress = true

    try {
      const response = await fetch('/api/presence-settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...data,
          clientTimestamp: this.lastSyncTime || new Date(0).toISOString(),
          force,
        }),
      })

      const result = await response.json()

      if (response.status === 409 && result.error === 'sync_conflict') {
        if (this.conflictCallback) {
          await this.conflictCallback(result)
        }
        return { success: false, conflict: result }
      }

      if (!response.ok) {
        throw new Error(`Failed to save settings: ${result.error || response.statusText}`)
      }

      if (result.syncedAt) {
        this.saveLastSyncTime(result.syncedAt)
      }

      this.pendingChanges = {}
      return { success: true }
    } finally {
      this.syncInProgress = false
      
      if (Object.keys(this.pendingChanges).length > 0) {
        const pending = this.pendingChanges
        this.pendingChanges = {}
        setTimeout(() => this.savePresenceSettings(pending), 1000)
      }
    }
  }

  async getServerState(): Promise<{ serverState: PresenceData; lastDevice: string | null; lastSyncedAt: string | null }> {
    const response = await fetch('/api/presence-settings/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action: 'get_server_state' }),
    })

    if (!response.ok) {
      throw new Error(`Failed to get server state: ${response.statusText}`)
    }

    return response.json()
  }

  async forceSync(deviceId?: string): Promise<{ message: string; deviceId: string; syncedAt: string }> {
    const response = await fetch('/api/presence-settings/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        action: 'force_sync', 
        deviceId: deviceId || this.deviceId 
      }),
    })

    if (!response.ok) {
      throw new Error(`Failed to force sync: ${response.statusText}`)
    }

    const result = await response.json()
    this.saveLastSyncTime(result.syncedAt)
    return result
  }

  async markConflictResolved(): Promise<void> {
    const response = await fetch('/api/presence-settings/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action: 'mark_conflict_resolved' }),
    })

    if (!response.ok) {
      throw new Error(`Failed to mark conflict resolved: ${response.statusText}`)
    }
  }

  startAutoSync(intervalMs = 30000) {
    if (this.syncInterval) {
      clearInterval(this.syncInterval)
    }

    this.syncInterval = setInterval(async () => {
      try {
        const data = await this.fetchPresenceSettings()
        if (data.needsSync) {
          window.dispatchEvent(new CustomEvent('presence-sync-update', { detail: data }))
        }
      } catch (error) {
        console.error('Auto-sync failed:', error)
      }
    }, intervalMs)
  }

  stopAutoSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval)
      this.syncInterval = null
    }
  }

  onConflict(callback: (conflict: ConflictResponse) => Promise<void>) {
    this.conflictCallback = callback
  }

  getDeviceId(): string {
    return this.deviceId
  }

  getLastSyncTime(): string | null {
    return this.lastSyncTime
  }

  isSyncInProgress(): boolean {
    return this.syncInProgress
  }
}

export const cloudSync = new CloudSyncService()
export type { PresenceData, SyncResponse, ConflictResponse }
