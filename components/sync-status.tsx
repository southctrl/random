"use client"

import { useState, useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Cloud, CloudOff, RefreshCw, AlertTriangle } from 'lucide-react'

interface SyncStatusProps {
  lastSyncTime: string | null
  isCurrentDevice: boolean
  syncInProgress: boolean
  error: string | null
  onForceSync?: () => Promise<void>
  showDetails?: boolean
}

export function SyncStatus({ 
  lastSyncTime, 
  isCurrentDevice, 
  syncInProgress, 
  error, 
  onForceSync,
  showDetails = false 
}: SyncStatusProps) {
  const [timeAgo, setTimeAgo] = useState<string>('')

  useEffect(() => {
    const updateTimeAgo = () => {
      if (!lastSyncTime) {
        setTimeAgo('Never')
        return
      }

      const now = new Date()
      const lastSync = new Date(lastSyncTime)
      const diffMs = now.getTime() - lastSync.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMins / 60)
      const diffDays = Math.floor(diffHours / 24)

      if (diffMins < 1) {
        setTimeAgo('Just now')
      } else if (diffMins < 60) {
        setTimeAgo(`${diffMins}m ago`)
      } else if (diffHours < 24) {
        setTimeAgo(`${diffHours}h ago`)
      } else {
        setTimeAgo(`${diffDays}d ago`)
      }
    }

    updateTimeAgo()
    const interval = setInterval(updateTimeAgo, 30000)

    return () => clearInterval(interval)
  }, [lastSyncTime])

  const getStatusColor = () => {
    if (error) return 'destructive'
    if (syncInProgress) return 'secondary'
    if (!lastSyncTime) return 'outline'
    if (!isCurrentDevice) return 'secondary'
    return 'default'
  }

  const getStatusIcon = () => {
    if (error) return <AlertTriangle className="h-3 w-3" />
    if (syncInProgress) return <RefreshCw className="h-3 w-3 animate-spin" />
    if (!lastSyncTime) return <CloudOff className="h-3 w-3" />
    return <Cloud className="h-3 w-3" />
  }

  const getStatusText = () => {
    if (error) return 'Sync Error'
    if (syncInProgress) return 'Syncing...'
    if (!lastSyncTime) return 'Not Synced'
    if (!isCurrentDevice) return 'Other Device'
    return 'Synced'
  }

  const getTooltipText = () => {
    if (error) return `Sync error: ${error}`
    if (syncInProgress) return 'Syncing changes to cloud...'
    if (!lastSyncTime) return 'No data synced to cloud yet'
    if (!isCurrentDevice) return `Last synced from another device ${timeAgo}`
    return `Last synced ${timeAgo}`
  }

  if (!showDetails) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant={getStatusColor()} className="gap-1">
              {getStatusIcon()}
              {getStatusText()}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <p>{getTooltipText()}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return (
    <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg">
      <Badge variant={getStatusColor()} className="gap-1">
        {getStatusIcon()}
        {getStatusText()}
      </Badge>
      
      {lastSyncTime && (
        <span className="text-sm text-muted-foreground">
          {timeAgo}
        </span>
      )}
      
      {!isCurrentDevice && (
        <Badge variant="outline" className="text-xs">
          Other Device
        </Badge>
      )}
      
      {onForceSync && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onForceSync}
          disabled={syncInProgress}
          className="h-6 px-2"
        >
          <RefreshCw className={`h-3 w-3 ${syncInProgress ? 'animate-spin' : ''}`} />
        </Button>
      )}
      
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  )
}
