"use client"

import { CloudSyncExample } from '@/components/cloud-sync-example'

export default function SyncTestPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container py-8">
        <h1 className="text-3xl font-bold mb-8">Cloud Sync Test</h1>
        <CloudSyncExample />
      </div>
    </div>
  )
}
