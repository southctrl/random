"use client"

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ConflictResponse } from '@/lib/sync-service'

interface SyncConflictDialogProps {
  open: boolean
  conflict: ConflictResponse | null
  onResolve: (choice: 'server' | 'client') => Promise<void>
  onClose?: () => void
}

export function SyncConflictDialog({ open, conflict, onResolve, onClose }: SyncConflictDialogProps) {
  const [resolving, setResolving] = useState(false)

  const handleResolve = async (choice: 'server' | 'client') => {
    setResolving(true)
    try {
      await onResolve(choice)
      onClose?.()
    } catch (error) {
      console.error('Failed to resolve conflict:', error)
    } finally {
      setResolving(false)
    }
  }

  const formatTime = (timeString: string) => {
    return new Date(timeString).toLocaleString()
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Sync Conflict Detected</DialogTitle>
          <DialogDescription>
            Your presence settings were updated on another device
          </DialogDescription>
        </DialogHeader>
        
        {conflict && (
          <div className="space-y-4">
            <Alert>
              <AlertDescription>
                <strong>Device:</strong> {conflict.lastDevice}<br />
                <strong>Last updated:</strong> {formatTime(conflict.serverTime)}
              </AlertDescription>
            </Alert>
            
            <div className="text-sm text-muted-foreground">
              <p>Choose which version you want to keep:</p>
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li><strong>Server version:</strong> Latest changes from the other device</li>
                <li><strong>Your version:</strong> Changes you made on this device</li>
              </ul>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleResolve('client')}
            disabled={resolving}
          >
            {resolving ? 'Resolving...' : 'Keep My Changes'}
          </Button>
          <Button
            onClick={() => handleResolve('server')}
            disabled={resolving}
          >
            {resolving ? 'Resolving...' : 'Use Server Version'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
