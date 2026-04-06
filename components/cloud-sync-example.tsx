"use client"

import { useState } from 'react'
import { useCloudSync } from '@/hooks/use-cloud-sync'
import { SyncStatus } from '@/components/sync-status'
import { SyncConflictDialog } from '@/components/sync-conflict-dialog'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'

interface PresenceSettings {
  rich?: {
    name?: string
    details?: string
    state?: string
  }
  custom?: {
    text?: string
    emoji?: string
  }
  spotify?: {
    title?: string
    artists?: string[]
    album?: string
  }
}

export function CloudSyncExample() {
  const [showConflictDialog, setShowConflictDialog] = useState(false)
  const [conflictData, setConflictData] = useState<any>(null)
  const [localSettings, setLocalSettings] = useState<PresenceSettings>({
    rich: { name: 'Example Activity', details: 'Working on something', state: 'Focused' },
    custom: { text: 'Custom status', emoji: '💻' },
    spotify: { title: 'Example Song', artists: ['Artist'], album: 'Example Album' }
  })

  const {
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
    refresh
  } = useCloudSync({
    autoSync: true,
    syncInterval: 30000,
    onConflict: async (conflict) => {
      setConflictData(conflict)
      setShowConflictDialog(true)
    }
  })

  const handleSave = async () => {
    const success = await saveSettings(localSettings)
    if (success) {
      console.log('Settings saved successfully')
    }
  }

  const handleConflictResolve = async (choice: 'server' | 'client') => {
    await resolveConflict(choice)
    setShowConflictDialog(false)
    setConflictData(null)
    
    if (choice === 'server') {
      setLocalSettings(data)
    }
  }

  if (loading) {
    return <div className="p-6">Loading...</div>
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Cloud Sync Demo
            <SyncStatus
              lastSyncTime={lastSyncTime}
              isCurrentDevice={isCurrentDevice}
              syncInProgress={syncInProgress}
              error={error}
              onForceSync={forceSync}
              showDetails={false}
            />
          </CardTitle>
          <CardDescription>
            Test cloud sync functionality across devices and browsers
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <Label>Device ID</Label>
              <Badge variant="outline" className="text-xs">
                {deviceId}
              </Badge>
            </div>
            <div>
              <Label>Last Sync</Label>
              <Badge variant="outline" className="text-xs">
                {lastSyncTime ? new Date(lastSyncTime).toLocaleString() : 'Never'}
              </Badge>
            </div>
          </div>

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Rich Presence Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="rich-name">Activity Name</Label>
            <Input
              id="rich-name"
              value={localSettings.rich?.name || ''}
              onChange={(e) => setLocalSettings(prev => ({
                ...prev,
                rich: { ...prev.rich, name: e.target.value }
              }))}
            />
          </div>
          <div>
            <Label htmlFor="rich-details">Details</Label>
            <Input
              id="rich-details"
              value={localSettings.rich?.details || ''}
              onChange={(e) => setLocalSettings(prev => ({
                ...prev,
                rich: { ...prev.rich, details: e.target.value }
              }))}
            />
          </div>
          <div>
            <Label htmlFor="rich-state">State</Label>
            <Input
              id="rich-state"
              value={localSettings.rich?.state || ''}
              onChange={(e) => setLocalSettings(prev => ({
                ...prev,
                rich: { ...prev.rich, state: e.target.value }
              }))}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Custom Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="custom-text">Status Text</Label>
            <Input
              id="custom-text"
              value={localSettings.custom?.text || ''}
              onChange={(e) => setLocalSettings(prev => ({
                ...prev,
                custom: { ...prev.custom, text: e.target.value }
              }))}
            />
          </div>
          <div>
            <Label htmlFor="custom-emoji">Emoji</Label>
            <Input
              id="custom-emoji"
              value={localSettings.custom?.emoji || ''}
              onChange={(e) => setLocalSettings(prev => ({
                ...prev,
                custom: { ...prev.custom, emoji: e.target.value }
              }))}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button 
          onClick={handleSave} 
          disabled={syncInProgress}
        >
          {syncInProgress ? 'Saving...' : 'Save to Cloud'}
        </Button>
        <Button 
          variant="outline" 
          onClick={refresh}
          disabled={syncInProgress}
        >
          Refresh
        </Button>
        <Button 
          variant="outline" 
          onClick={forceSync}
          disabled={syncInProgress}
        >
          Force Sync
        </Button>
      </div>

      <SyncConflictDialog
        open={showConflictDialog}
        conflict={conflictData}
        onResolve={handleConflictResolve}
        onClose={() => setShowConflictDialog(false)}
      />
    </div>
  )
}
