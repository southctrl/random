"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { BrandedBackground } from "@/components/branded-background"
import { RpcUnreachableOverlay } from "@/components/rpc-unreachable-overlay"
import { RpcSidebar } from "@/components/layout/rpc-sidebar"
import { MobileHeader } from "@/components/layout/mobile-sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { useCloudSettings } from "@/hooks/use-cloud-settings"
import { useCloudSyncManager } from "@/hooks/use-cloud-sync-manager"
import { useNavigationProtection } from "@/hooks/use-navigation-protection"
import { SaveChanges } from "@/components/layout/SaveChanges"
import { UnsavedChangesDialog } from "@/components/layout/UnsavedChangesDialog"
import {
    Gamepad2,
    Music,
    Sparkles,
    LogOut,
    RefreshCw,
    Trash2,
    Circle,
    Loader2,
    User,
    Wifi,
    WifiOff,
    Settings,
    ChevronDown,
    ChevronRight,
    Check,
    Layers,
    Plus,
    ArrowLeft,
    Edit,
    Play,
    Pause,
    PowerOff,
} from "lucide-react"

const API_BASE = "/api/rpc"

type Status = "online" | "idle" | "dnd" | "invisible"

interface CurrentStatus {
    connected?: boolean
    avatar_url?: string
    status?: string
    custom_status?: {
        emoji: string
        text: string
    }
    activity?: {
        name: string
        details?: string
        state?: string
    }
    spotify?: {
        song: string
        artist: string
    }
}

interface StackableRpc {
    id: string
    name: string
    details: string
    state: string
    type: string
    platform: string
    streaming_url: string
    large_image_url: string
    large_text: string
    small_image_url: string
    small_text: string
    button1_label: string
    button1_url: string
    button2_label: string
    button2_url: string
    start: string
    end: string
    enabled: boolean
}

const navItems = [
    {
        category: "RPC",
        items: [
            { id: "status", label: "Status", icon: "status" },
            { id: "custom", label: "Custom Status", icon: "custom" },
            { id: "rich", label: "Rich Presence", icon: "rich" },
            { id: "spotify", label: "Spotify Lyrics", icon: "spotify" },
        ]
    }
]

function isRpcProxyDown(res: Response, body: unknown): boolean {
    if (res.ok) return false
    if (res.status < 500) return false
    if (!body || typeof body !== "object") return false
    const err = (body as { error?: string; detail?: string }).error
    const detail = (body as { error?: string; detail?: string }).detail
    const msg = `${err ?? ""} ${detail ?? ""}`.toLowerCase()
    return (
        msg.includes("proxy") ||
        msg.includes("fetch failed") ||
        msg.includes("econnrefused")
    )
}

async function fetchStatus(
    token: string
): Promise<{ unreachable: boolean; data: CurrentStatus | null }> {
    try {
        const res = await fetch(`${API_BASE}/status`, {
            headers: { Authorization: `Bearer ${token}` },
        })
        const body = await res.json().catch(() => null)
        if (res.ok && body && typeof body === "object") {
            if (body.connected === false) {
                return { unreachable: false, data: null }
            }
            return { unreachable: false, data: body as CurrentStatus }
        }
        if (isRpcProxyDown(res, body)) {
            return { unreachable: true, data: null }
        }
        return { unreachable: false, data: null }
    } catch (err) {
        console.error("Failed to fetch status:", err)
        return { unreachable: true, data: null }
    }
}

const Icon = ({
    name,
    className = "h-4 w-4",
}: {
    name: string
    className?: string
}) => {
    switch (name) {
        case "status":
            return <Circle className={className} />
        case "rich":
            return <Gamepad2 className={className} />
        case "custom":
            return <Sparkles className={className} />
        case "spotify":
            return <Music className={className} />
        default:
            return <Circle className={className} />
    }
}

const StatusDot = ({
    status,
    className = "h-3 w-3",
}: {
    status: Status
    className?: string
}) => {
    const colors: Record<Status, string> = {
        online: "fill-green-500 text-green-500",
        idle: "fill-yellow-500 text-yellow-500",
        dnd: "fill-red-500 text-red-500",
        invisible: "fill-gray-500 text-gray-500",
    }
    return <Circle className={`${className} ${colors[status]}`} />
}

const defaultStackableRpc: StackableRpc = {
    id: "",
    name: "",
    details: "",
    state: "",
    type: "Playing",
    platform: "",
    streaming_url: "",
    large_image_url: "",
    large_text: "",
    small_image_url: "",
    small_text: "",
    button1_label: "",
    button1_url: "",
    button2_label: "",
    button2_url: "",
    start: "",
    end: "",
    enabled: true,
}

export default function StackablesPage() {
    const router = useRouter()
    const { data: sessionAuth, isPending: sessionPending } =
        authClient.useSession()
    const [loading, setLoading] = useState(false)
    const [token, setToken] = useState<string | null>(null)
    const [currentStatus, setCurrentStatus] = useState<CurrentStatus | null>(
        null
    )
    const [refreshing, setRefreshing] = useState(false)
    const [connected, setConnected] = useState(false)
    const [rpcUnreachable, setRpcUnreachable] = useState(false)
    const [rpcRetrying, setRpcRetrying] = useState(false)
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(["RPC"]))
    const [connectionAttempts, setConnectionAttempts] = useState(0)
    const [connectionError, setConnectionError] = useState<string | null>(null)
    const [isConnecting, setIsConnecting] = useState(false)
    const [isRotating, setIsRotating] = useState(false)
    const [currentRpcIndex, setCurrentRpcIndex] = useState(0)
    const [activeInstances, setActiveInstances] = useState<Set<string>>(new Set())

    const { isSyncing } = useCloudSettings()
    const { saveToCloud } = useCloudSyncManager()

    const validateToken = useCallback(async (tokenToValidate: string): Promise<boolean> => {
        try {
            const response = await fetch("/api/user/validate-token", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: tokenToValidate }),
            })
            
            if (!response.ok) {
                const errorData = await response.json()
                if (errorData.code === "INVALID_TOKEN" || errorData.code === "TOKEN_EXPIRED") {
                    localStorage.removeItem("discord_token")
                    localStorage.removeItem("discord_token_validated")
                    router.push("/invalid-token")
                    return false
                }
            }
            return response.ok
        } catch {
            return false
        }
    }, [router])

    const getInitialStackables = (): StackableRpc[] => {
        if (typeof window === "undefined") return []
        
        const saved = localStorage.getItem("stackable_rpcs")
        if (saved) {
            try {
                return JSON.parse(saved)
            } catch {
                return []
            }
        }
        return []
    }

    const [stackables, setStackables] = useState<StackableRpc[]>(getInitialStackables())
    const [editingRpc, setEditingRpc] = useState<StackableRpc | null>(null)
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [showDialog, setShowDialog] = useState(false)
    const [lastSynced, setLastSynced] = useState<Date | null>(null)

    const confirmNavigation = useCallback(() => {
        setShowDialog(false)
    }, [])

    const cancelNavigation = useCallback(() => {
        setShowDialog(false)
    }, [])

    const { showDialog: showNavigationDialog, onConfirm: handleNavigationConfirm, onCancel: handleNavigationCancel } = useNavigationProtection({
        hasUnsavedChanges,
        onConfirmNavigation: () => {
            console.log("🔒 [STACKABLES] Navigation confirmed")
            confirmNavigation()
        },
        onCancelNavigation: () => {
            console.log("🔒 [STACKABLES] Navigation cancelled")
            cancelNavigation()
        },
    })

    useEffect(() => {
        if (!hasUnsavedChanges) return
        
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            e.preventDefault()
            e.returnValue = ""
        }
        
        window.addEventListener("beforeunload", handleBeforeUnload)
        return () => window.removeEventListener("beforeunload", handleBeforeUnload)
    }, [hasUnsavedChanges])


    useEffect(() => {
        if (sessionPending) return
        const init = async () => {
            if (!sessionAuth?.session) {
                router.push("/login")
                return
            }
            const discordToken = localStorage.getItem("discord_token")
            if (!discordToken) {
                router.push("/onboarding")
                return
            }
            
            const isValid = await validateToken(discordToken)
            if (!isValid) return
            
            setToken(discordToken)
            
            const { unreachable, data } = await fetchStatus(discordToken)
            setRpcUnreachable(unreachable)
            setCurrentStatus(data)
            const isConnected = !unreachable && data !== null
            setConnected(isConnected)
            
            if (!isConnected) {
                handleConnect()
            }
        }
        init()
    }, [router, sessionAuth, sessionPending, validateToken])

    const refresh = async () => {
        if (!token) return
        setRefreshing(true)
        const { unreachable, data } = await fetchStatus(token)
        console.log("Refresh data:", data)
        setRpcUnreachable(unreachable)
        setCurrentStatus(data)
        setConnected(!unreachable && data !== null)
        setTimeout(() => setRefreshing(false), 300)
    }

    const retryRpcConnection = async () => {
        if (!token) return
        setRpcRetrying(true)
        await refresh()
        setRpcRetrying(false)
    }

    useEffect(() => {
        if (!rpcUnreachable || !token) return
        const id = setInterval(async () => {
            const { unreachable, data } = await fetchStatus(token)
            setRpcUnreachable(unreachable)
            setCurrentStatus(data)
            setConnected(!unreachable && data !== null)
        }, 4000)
        return () => clearInterval(id)
    }, [rpcUnreachable, token])

    const notify = (type: "success" | "error", msg: string) => {
        if (type === "success") toast.success(msg)
        else toast.error(msg)
    }

    const signOut = async () => {
        await authClient.signOut()
        router.push("/login")
    }

    const api = async (endpoint: string, body?: object, verb = "POST") => {
        if (!token) return null
        setLoading(true)
        try {
            const res = await fetch(`${API_BASE}/${endpoint}`, {
                method: verb,
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: body ? JSON.stringify(body) : undefined,
            })
            const data = await res.json().catch(() => ({}))
            if (isRpcProxyDown(res, data)) {
                setRpcUnreachable(true)
                notify("error", "Cannot reach RPC server")
            } else {
                setRpcUnreachable(false)
            }
            if (res.ok) {
                notify("success", data.message || "Done")
                console.log("API call successful, calling refresh...")
                refresh()
            } else if (!isRpcProxyDown(res, data)) {
                notify("error", data.error || "Something went wrong")
            }
            return data
        } catch {
            setRpcUnreachable(true)
            notify("error", "Connection failed")
        } finally {
            setLoading(false)
        }
        return null
    }

    const handleConnect = async () => {
        if (!token) return
        
        setIsConnecting(true)
        
        try {
            const res = await fetch(`${API_BASE}/login`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ token }),
            })
            
            if (res.ok) {
                const { unreachable, data } = await fetchStatus(token)
                setRpcUnreachable(unreachable)
                setCurrentStatus(data)
                setConnected(!unreachable && data !== null)
                setConnectionAttempts(0)
                setConnectionError(null)
                setIsConnecting(false)
                return
            }
            
            setConnectionError("Connection failed")
        } catch (error) {
            setConnectionError("Connection failed")
        }
        
        setIsConnecting(false)
    }

    const toggleStackableInstance = async (rpc: StackableRpc) => {
        if (!rpc.enabled) {
            toast.error("Enable the stackable RPC first")
            return
        }
        
        if (activeInstances.has(rpc.id)) {
            await stopStackableInstance(rpc.id)
        } else {
            await startStackableInstance(rpc)
        }
    }

    const getConnectButtonText = () => {
        if (isConnecting) return "Connecting..."
        if (connectionError) return `Reconnect: ${connectionError}` 
        return "Connect"
    }

    const toggleCategory = (category: string) => {
        setExpandedCategories(prev => {
            const newSet = new Set(prev)
            if (newSet.has(category)) {
                newSet.delete(category)
            } else {
                newSet.add(category)
            }
            return newSet
        })
    }

    const addNewRpc = () => {
        if (stackables.length >= 3) {
            toast.error("Maximum 3 stackable RPCs allowed")
            return
        }
        
        const newRpc: StackableRpc = {
            ...defaultStackableRpc,
            id: Date.now().toString(),
        }
        setStackables(prev => [...prev, newRpc])
        setEditingRpc(newRpc)
        setHasUnsavedChanges(true)
    }

    const startStackableInstance = async (rpc: StackableRpc) => {
        if (!token) return
        
        try {
            const data: Record<string, string | number> = {
                type: rpc.type || "",
                name: rpc.name || "Expel Selfbot",
            }
            
            if (rpc.details) data.details = rpc.details
            if (rpc.state) data.state = rpc.state
            if (rpc.streaming_url) data.streaming_url = rpc.streaming_url
            if (rpc.platform) data.platform = rpc.platform
            if (rpc.large_image_url) data.large_image_url = rpc.large_image_url
            if (rpc.large_text) data.large_text = rpc.large_text
            if (rpc.small_image_url) data.small_image_url = rpc.small_image_url
            if (rpc.small_text) data.small_text = rpc.small_text
            if (rpc.start) data.start = parseInt(rpc.start)
            if (rpc.end) data.end = parseInt(rpc.end)
            if (rpc.button1_label) data.button1_label = rpc.button1_label
            if (rpc.button1_url) data.button1_url = rpc.button1_url
            if (rpc.button2_label) data.button2_label = rpc.button2_label
            if (rpc.button2_url) data.button2_url = rpc.button2_url
            
            await api("rpc/set-rich-presence", data)
            setActiveInstances(prev => new Set([...prev, rpc.id]))
            toast.success(`Started stackable RPC: ${rpc.name || "Unnamed RPC"}`)
        } catch (error) {
            console.error("Failed to start stackable RPC:", error)
            toast.error("Failed to start stackable RPC")
        }
    }

    const stopStackableInstance = async (rpcId: string) => {
        try {
            let currentTimestamps: { start: number | null; end: number | null } | null = null
            try {
                const response = await api("current-activities")
                if (response.activities && response.activities.length > 0) {
                    const currentActivity = response.activities.find((activity: any) => {
                        return activity.name && activity.name.toLowerCase().includes('playstation')
                    })
                    
                    if (currentActivity && currentActivity.timestamps) {
                        currentTimestamps = {
                            start: currentActivity.timestamps.start || null,
                            end: currentActivity.timestamps.end || null
                        }
                        console.log(`[STACKABLES] Found current Discord activity timestamps:`, currentTimestamps)
                    }
                }
            } catch (error) {
                console.log(`[STACKABLES] Failed to get current activities:`, error)
            }
            
            const otherActiveInstances = Array.from(activeInstances).filter(id => id !== rpcId)
            const otherActiveRpcs = otherActiveInstances.map(id => {
                const rpc = stackables.find(r => r.id === id)
                if (!rpc) return null
                
                const timestamps = currentTimestamps || {
                    start: rpc.start || null,
                    end: rpc.end || null
                }
                
                console.log(`[STACKABLES] Found RPC ${rpc.name} with timestamps:`, timestamps)
                
                return { ...rpc, originalId: id, ...timestamps }
            }).filter((rpc): rpc is StackableRpc & { originalId: string } => rpc !== null)
            
            console.log(`[STACKABLES] Stopping RPC ${rpcId}, other active: ${otherActiveInstances.join(', ')}`)
            console.log(`[STACKABLES] Preserving timestamps for: ${otherActiveRpcs.map(r => `${r.name}: start=${r.start || 'null'}, end=${r.end || 'null'}`).join(', ')}`)
            
            await api("clear-id", { instanceId: rpcId })
            
            setActiveInstances(prev => {
                const newSet = new Set(prev)
                newSet.delete(rpcId)
                return newSet
            })
            
            toast.success(`Stopped stackable RPC: ${rpcId}`)
            
            if (otherActiveRpcs.length > 0) {
                console.log(`[STACKABLES] Restarting ${otherActiveRpcs.length} other instances with preserved timestamps...`)
                setTimeout(async () => {
                    for (const rpc of otherActiveRpcs) {
                        console.log(`[STACKABLES] Restarting RPC: ${rpc.name} with preserved timestamps: start=${rpc.start || 'null'}, end=${rpc.end || 'null'}`)
                        try {
                            await startStackableInstance(rpc)
                            await new Promise(resolve => setTimeout(resolve, 300))
                        } catch (error) {
                            console.error(`[STACKABLES] Failed to restart RPC ${rpc.originalId}:`, error)
                        }
                    }
                }, 800)
            }
        } catch (error) {
            console.error("Failed to stop stackable RPC:", error)
            toast.error("Failed to stop stackable RPC")
        }
    }

    const editRpc = (rpc: StackableRpc) => {
        setEditingRpc(rpc)
    }

    const deleteRpc = async (id: string) => {
        if (activeInstances.has(id)) {
            await stopStackableInstance(id)
        }
        
        setStackables(prev => prev.filter(rpc => rpc.id !== id))
        if (editingRpc?.id === id) {
            setEditingRpc(null)
        }
        setHasUnsavedChanges(true)
    }

    const toggleRpcEnabled = (id: string) => {
        setStackables(prev => prev.map(rpc => 
            rpc.id === id ? { ...rpc, enabled: !rpc.enabled } : rpc
        ))
        setHasUnsavedChanges(true)
    }

    const updateEditingRpc = (field: keyof StackableRpc, value: string | boolean) => {
        if (!editingRpc) return
        
        console.log("[STACKABLES] Updating RPC:", field, value)
        const updated = { ...editingRpc, [field]: value }
        setEditingRpc(updated)
        
        setStackables(prev => prev.map(rpc => 
            rpc.id === updated.id ? updated : rpc
        ))
        console.log("[STACKABLES] Setting hasUnsavedChanges to true")
        setHasUnsavedChanges(true)
    }

    const saveStackables = async () => {
        setIsSaving(true)
        try {
            localStorage.setItem("stackable_rpcs", JSON.stringify(stackables))
            
            const success = await saveToCloud({
                game_rpc_settings: stackables as unknown as Record<string, unknown>,
            })
            
            if (success) {
                toast.success("Stackable RPCs saved to cloud")
                setHasUnsavedChanges(false)
                setLastSynced(new Date())
                
                if (editingRpc) {
                    const savedRpc = stackables.find(rpc => rpc.id === editingRpc.id)
                    if (savedRpc) {
                        setEditingRpc(savedRpc)
                        console.log(`[STACKABLES] Updated editing RPC after save: ${savedRpc.name || 'Unnamed'}`)
                        
                        if (savedRpc.enabled && activeInstances.has(savedRpc.id)) {
                            console.log(`[STACKABLES] Restarting active RPC ${savedRpc.name} with new changes`)
                            
                            await stopStackableInstance(savedRpc.id)
                            setTimeout(async () => {
                                await startStackableInstance(savedRpc)
                            }, 500)
                        } else if (savedRpc.enabled && !activeInstances.has(savedRpc.id)) {
                            console.log(`[STACKABLES] Starting enabled RPC ${savedRpc.name} after save`)
                            await startStackableInstance(savedRpc)
                        }
                    }
                }
                
                for (const rpc of stackables) {
                    if (rpc.enabled && !activeInstances.has(rpc.id)) {
                        await startStackableInstance(rpc)
                    }
                }
            } else {
                toast.error("Failed to save to cloud")
            }
        } catch (error) {
            console.error("Save failed:", error)
            toast.error("Failed to save changes")
        } finally {
            setIsSaving(false)
        }
    }

    const startRotation = async () => {
        const enabledRpcs = stackables.filter(rpc => rpc.enabled)
        if (enabledRpcs.length === 0) {
            toast.error("No enabled RPCs to rotate")
            return
        }

        setIsRotating(true)
        let index = 0

        const rotate = async () => {
            if (!isRotating) return
            
            const rpc = enabledRpcs[index]
            const data: Record<string, string | number> = {
                type: rpc.type || "",
                name: rpc.name || "Custom Status",
            }
            
            if (rpc.details) data.details = rpc.details
            if (rpc.state) data.state = rpc.state
            if (rpc.streaming_url) data.streaming_url = rpc.streaming_url
            if (rpc.platform) data.platform = rpc.platform
            if (rpc.large_image_url) data.large_image_url = rpc.large_image_url
            if (rpc.large_text) data.large_text = rpc.large_text
            if (rpc.small_image_url) data.small_image_url = rpc.small_image_url
            if (rpc.small_text) data.small_text = rpc.small_text
            if (rpc.start) data.start = parseInt(rpc.start)
            if (rpc.end) data.end = parseInt(rpc.end)
            if (rpc.button1_label) data.button1_label = rpc.button1_label
            if (rpc.button1_url) data.button1_url = rpc.button1_url
            if (rpc.button2_label) data.button2_label = rpc.button2_label
            if (rpc.button2_url) data.button2_url = rpc.button2_url
            
            await api("rpc/set-rich-presence", data)
            
            index = (index + 1) % enabledRpcs.length
            setCurrentRpcIndex(index)
            
            setTimeout(rotate, 10000)
        }

        rotate()
        toast.success("Started RPC rotation")
    }

    const stopRotation = () => {
        setIsRotating(false)
        toast.success("Stopped RPC rotation")
    }

    if (sessionPending) {
        return (
            <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
                <BrandedBackground />
                <Loader2 className="relative z-10 h-10 w-10 animate-spin text-white/80" />
            </div>
        )
    }

    return (
        <div className="relative min-h-screen overflow-hidden">
            <BrandedBackground />
            {rpcUnreachable && (
                <RpcUnreachableOverlay
                    onRetry={retryRpcConnection}
                    retrying={rpcRetrying || refreshing}
                />
            )}
            <div
                className={`relative z-10 flex min-h-screen transition-[filter,opacity] duration-200 ${rpcUnreachable ? "pointer-events-none brightness-[0.55]" : ""}`}
                aria-hidden={rpcUnreachable}
            >
            <RpcSidebar
                onSignOut={signOut}
                connected={connected}
                status={(connected
                    ? (currentStatus?.status as Status | undefined)
                    : "invisible") ?? "invisible"}
                avatarUrl={
                    currentStatus?.avatar_url ??
                    sessionAuth?.user?.image ??
                    null
                }
                userName={sessionAuth?.user?.name || "User"}
                isSyncing={isSyncing}
                onConnect={handleConnect}
                isConnecting={isConnecting}
            />

            <div className="flex flex-1 flex-col">
                <MobileHeader 
                    title="Stackable RPCs" 
                    onRefresh={refresh}
                    refreshing={refreshing}
                    onClear={() => api("clear")}
                    loading={loading}
                    connected={connected}
                />
                
                <TopBar
                    onRefresh={refresh}
                    onClear={() => api("clear")}
                    refreshing={refreshing}
                    loading={loading}
                    connected={connected}
                />

                <main className="flex-1 px-4 py-8 pt-20 md:pt-8 sm:px-6 lg:px-10">
                    <div className="mx-auto w-full max-w-6xl">
                        <div className="grid gap-6 lg:grid-cols-[1.8fr_1.2fr]">
                            <div>
                                {editingRpc && (
                                    <StackableEditor
                                        rpc={editingRpc}
                                        onUpdate={updateEditingRpc}
                                        loading={loading}
                                        showDialog={showDialog}
                                        setShowDialog={setShowDialog}
                                        confirmNavigation={confirmNavigation}
                                        cancelNavigation={cancelNavigation}
                                        showNavigationDialog={showNavigationDialog}
                                        handleNavigationConfirm={handleNavigationConfirm}
                                        handleNavigationCancel={handleNavigationCancel}
                                    />
                                )}
                            </div>
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-semibold text-white">
                                        Stackable RPCs
                                    </h3>
                                    <Button
                                        onClick={addNewRpc}
                                        className="gap-2 rounded-lg border-purple-500/25 bg-purple-500/10 text-white/90 hover:border-purple-400/40 hover:bg-purple-500/20"
                                    >
                                        <Plus className="h-4 w-4" />
                                        Add RPC
                                    </Button>
                                </div>
                                
                                <div className="space-y-1">
                                    {stackables.map((rpc) => (
                                        <div
                                            key={rpc.id}
                                            className={`rounded-lg border ${activeInstances.has(rpc.id) ? 'border-green-500/25 bg-green-500/10' : rpc.enabled ? 'border-sky-500/25 bg-sky-500/10' : 'border-white/10 bg-black/35'} p-2 backdrop-blur-sm`}
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <div className={`h-3 w-3 rounded-full border-2 transition-colors ${
                                                        activeInstances.has(rpc.id)
                                                            ? 'border-green-500 bg-green-500 animate-pulse'
                                                            : rpc.enabled 
                                                            ? 'border-sky-500 bg-sky-500' 
                                                            : 'border-gray-500 bg-gray-500'
                                                    }`} />
                                                    <div className="flex-1 min-w-0">
                                                        <div className="font-medium text-white text-sm truncate">
                                                            {rpc.name || "Unnamed RPC"}
                                                        </div>
                                                        <div className="text-xs text-white/60 truncate">
                                                            {rpc.details || "No details"}
                                                        </div>
                                                        {activeInstances.has(rpc.id) && (
                                                            <div className="flex items-center gap-1 text-xs text-green-400">
                                                                <div className="text-white/50">ID:</div>
                                                                <div className="font-mono">{rpc.id}</div>
                                                                <div className="text-white/50">•</div>
                                                                <div>Active</div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                                <div className="flex gap-1">
                                                    <Button
                                                        size="icon"
                                                        variant="ghost"
                                                        onClick={() => toggleStackableInstance(rpc)}
                                                        disabled={!rpc.enabled}
                                                        className="h-6 w-6 p-0"
                                                    >
                                                        <PowerOff 
                                                            className={`h-3.5 w-3.5 ${
                                                                activeInstances.has(rpc.id) 
                                                                    ? 'text-green-500' 
                                                                    : 'text-red-500'
                                                            }`} 
                                                        />
                                                    </Button>
                                                    <Button
                                                        size="icon"
                                                        variant="ghost"
                                                        onClick={() => editRpc(rpc)}
                                                        className="h-6 w-6 p-0 text-white/60 hover:text-white"
                                                    >
                                                        <Edit className="h-3.5 w-3.5" />
                                                    </Button>
                                                    <Button
                                                        size="icon"
                                                        variant="ghost"
                                                        onClick={() => deleteRpc(rpc.id)}
                                                        className="h-6 w-6 p-0 text-red-400 hover:text-red-300"
                                                    >
                                                        <Trash2 className="h-3.5 w-3.5" />
                                                    </Button>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                    
                                    {stackables.length === 0 && (
                                        <div className="rounded-lg border border-dashed border-white/10 bg-black/35 p-8 text-center">
                                            <Layers className="mx-auto h-12 w-12 text-white/20 mb-4" />
                                            <p className="text-white/60">
                                                No stackable RPCs yet. Create your first one!
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                        
                        <SaveChanges
                            show={hasUnsavedChanges}
                            saving={isSaving}
                            onSave={saveStackables}
                            isSyncing={isSyncing}
                            lastSynced={lastSynced}
                        />
                    </div>
                </main>
            </div>
            </div>
        </div>
    )
}

function TopBar({
    onRefresh,
    onClear,
    refreshing,
    loading,
    connected,
}: {
    onRefresh: () => void
    onClear: () => void
    refreshing: boolean
    loading: boolean
    connected: boolean
}) {
    return (
        <header className="hidden md:flex h-16 items-center justify-between border-b border-white/10 bg-black/20 px-6 backdrop-blur-sm">
            <div className="flex items-center gap-4">
                <Link
                    href="/rpc/rich"
                    className="flex items-center gap-2 text-sm text-white/60 hover:text-white/90 transition-colors"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Rich Presence
                </Link>
                <div>
                    <h2 className="text-lg font-semibold text-white">
                        Stackable RPCs
                    </h2>
                    <p className="text-xs text-white/45">
                        {connected
                            ? "Manage your stackable RPCs"
                            : "Reconnect to continue"}
                    </p>
                </div>
            </div>
            <div className="flex gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={onRefresh}
                    disabled={!connected || refreshing}
                    className="gap-2 border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    <RefreshCw
                        className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                    />
                    Refresh
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={onClear}
                    disabled={!connected || loading}
                    className="gap-2 border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    <Trash2 className="h-4 w-4" />
                    Clear
                </Button>
            </div>
        </header>
    )
}

function StackableEditor({
    rpc,
    onUpdate,
    loading,
    showDialog,
    setShowDialog,
    confirmNavigation,
    cancelNavigation,
    showNavigationDialog,
    handleNavigationConfirm,
    handleNavigationCancel,
}: {
    rpc: StackableRpc
    onUpdate: (field: keyof StackableRpc, value: string | boolean) => void
    loading: boolean
    showDialog: boolean
    setShowDialog: (open: boolean) => void
    confirmNavigation: () => void
    cancelNavigation: () => void
    showNavigationDialog: boolean
    handleNavigationConfirm: () => void
    handleNavigationCancel: () => void
}) {
    const activityTypes = [
        { value: "Competing", label: "Competing" },
        { value: "Listening", label: "Listening" },
        { value: "Playing", label: "Playing" },
        { value: "Streaming", label: "Streaming" },
        { value: "Watching", label: "Watching" },
    ].sort((a, b) => a.label.localeCompare(b.label))

    const [platforms, setPlatforms] = useState<Array<{ value: string; label: string }>>([])

    useEffect(() => {
        const fetchPlatforms = async () => {
            try {
                const res = await fetch(`${API_BASE}/platforms`)
                const data = await res.json()
                if (data.platforms) {
                    const sortedPlatforms = [...data.platforms].sort((a, b) => a.label.localeCompare(b.label))
                    setPlatforms(sortedPlatforms)
                }
            } catch (error) {
                console.error("Failed to fetch platforms:", error)
            }
        }
        
        fetchPlatforms()
    }, [])

    const set = (k: keyof StackableRpc, v: string) => {
        onUpdate(k, v)
    }

    return (
        <>
        <div className="rounded-xl border border-white/10 bg-black/35 p-6 backdrop-blur-sm">
            <h3 className="mb-6 flex items-center gap-2 text-base font-medium text-white">
                <Layers className="h-4 w-4 text-blue-400" />
                Edit Stackable RPC
            </h3>
            
            <form className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                        <Label htmlFor="type" className="text-white/80">Activity Type</Label>
                        <select
                            id="type"
                            value={rpc.type || ""}
                            onChange={(e) => set("type", e.target.value)}
                            className="w-full mt-1 rounded-lg border border-white/10 bg-black px-3 py-2 text-white hover:bg-sky-900 hover:border-sky-500 transition-colors"
                            disabled={loading}
                        >
                            <option value="">Select a type</option>
                            {activityTypes.map((type) => (
                                <option key={type.value} value={type.value}>
                                    {type.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <Label htmlFor="platform" className="text-white/80">Platform</Label>
                        <select
                            id="platform"
                            value={rpc.platform || ""}
                            onChange={(e) => set("platform", e.target.value)}
                            className="w-full mt-1 rounded-lg border border-white/10 bg-black px-3 py-2 text-white hover:bg-sky-900 hover:border-sky-500 transition-colors"
                            disabled={loading}
                        >
                            <option value="">Select platform</option>
                            {platforms.map((platform) => (
                                <option key={platform.value} value={platform.value}>
                                    {platform.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <Field
                        label="Streaming URL"
                        id="streaming_url"
                        value={rpc.streaming_url}
                        onChange={(v) => set("streaming_url", v)}
                        placeholder="https://www.twitch.tv/username"
                        type={(rpc.type === "Streaming" || rpc.type === "Watching") ? "text" : "hidden"}
                        disabled={loading}
                    />
                    <Field
                        label="Activity Name"
                        id="name"
                        value={rpc.name}
                        onChange={(v) => set("name", v)}
                        placeholder="Game Name"
                        disabled={loading}
                    />
                    <Field
                        label="Details"
                        id="details"
                        value={rpc.details}
                        onChange={(v) => set("details", v)}
                        placeholder="Playing Game"
                        disabled={loading}
                    />
                    <Field
                        label="State"
                        id="state"
                        value={rpc.state}
                        onChange={(v) => set("state", v)}
                        placeholder="In Match"
                        disabled={loading}
                    />
                    <Field
                        label="Large Image URL"
                        id="large_image_url"
                        value={rpc.large_image_url}
                        onChange={(v) => set("large_image_url", v)}
                        placeholder="https://..."
                        disabled={loading}
                    />
                    <Field
                        label="Large Image Text"
                        id="large_text"
                        value={rpc.large_text}
                        onChange={(v) => set("large_text", v)}
                        placeholder="Tooltip"
                        disabled={loading}
                    />
                    <Field
                        label="Small Image URL"
                        id="small_image_url"
                        value={rpc.small_image_url}
                        onChange={(v) => set("small_image_url", v)}
                        placeholder="https://..."
                        disabled={loading}
                    />
                    <Field
                        label="Small Image Text"
                        id="small_text"
                        value={rpc.small_text}
                        onChange={(v) => set("small_text", v)}
                        placeholder="Tooltip"
                        disabled={loading}
                    />
                    <Field
                        label="Start (ms)"
                        id="start"
                        value={rpc.start}
                        onChange={(v) => set("start", v)}
                        placeholder="1700000000000"
                        type="number"
                        disabled={loading}
                    />
                    <Field
                        label="End (ms)"
                        id="end"
                        value={rpc.end}
                        onChange={(v) => set("end", v)}
                        placeholder="1700003600000"
                        type="number"
                        disabled={loading}
                    />
                    <Field
                        label="Button 1 Label"
                        id="button1_label"
                        value={rpc.button1_label}
                        onChange={(v) => set("button1_label", v)}
                        placeholder="Play Now"
                        disabled={loading}
                    />
                    <Field
                        label="Button 1 URL"
                        id="button1_url"
                        value={rpc.button1_url}
                        onChange={(v) => set("button1_url", v)}
                        placeholder="https://..."
                        disabled={loading}
                    />
                    <Field
                        label="Button 2 Label"
                        id="button2_label"
                        value={rpc.button2_label}
                        onChange={(v) => set("button2_label", v)}
                        placeholder="Join Party"
                        disabled={loading}
                    />
                    <Field
                        label="Button 2 URL"
                        id="button2_url"
                        value={rpc.button2_url}
                        onChange={(v) => set("button2_url", v)}
                        placeholder="https://..."
                        disabled={loading}
                    />
                </div>
            </form>
        </div>
        <UnsavedChangesDialog
            open={showDialog}
            onOpenChange={setShowDialog}
            onConfirm={confirmNavigation}
            onCancel={cancelNavigation}
        />

        <UnsavedChangesDialog
            open={showNavigationDialog}
            onOpenChange={(open) => {
                if (!open) {
                    handleNavigationCancel()
                }
            }}
            onConfirm={handleNavigationConfirm}
            onCancel={handleNavigationCancel}
        />
        </>
    )
}

function Field({
    label,
    id,
    value,
    onChange,
    placeholder,
    type = "text",
    disabled = false,
}: {
    label: string
    id: string
    value: string
    onChange: (v: string) => void
    placeholder: string
    type?: string
    disabled?: boolean
}) {
    if (type === "hidden") return null
    
    return (
        <div className="space-y-2">
            <Label htmlFor={id} className="text-white/80">
                {label}
            </Label>
            <Input
                id={id}
                type={type}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                disabled={disabled}
                className="border-white/10 bg-black text-white hover:bg-sky-900 hover:border-sky-500 transition-colors"
            />
        </div>
    )
}
