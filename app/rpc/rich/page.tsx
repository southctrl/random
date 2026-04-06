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

export default function RichPage() {
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

    const { isSyncing } = useCloudSettings()

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
    }, [router, sessionAuth, sessionPending])

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
        let attempts = 0
        const maxAttempts = 5
        
        while (attempts < maxAttempts) {
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
                
                attempts++
                if (attempts < maxAttempts) {
                    await new Promise(resolve => setTimeout(resolve, 1000))
                }
            } catch (error) {
                attempts++
                if (attempts < maxAttempts) {
                    await new Promise(resolve => setTimeout(resolve, 1000))
                }
            }
        }
        
        setConnectionAttempts(maxAttempts)
        setConnectionError("Failed to establish connection after 5 attempts")
        setIsConnecting(false)
    }

    const getConnectButtonText = () => {
        if (isConnecting) return "Connecting..."
        if (connectionAttempts >= 5 && connectionError) return `Reconnection failed: ${connectionError}` 
        if (connectionAttempts > 0) return "Reconnect"
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
                    title="Rich Presence" 
                    onRefresh={refresh}
                    refreshing={refreshing}
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
                        <RichPanel
                            onSubmit={async (d) =>
                                await api("rpc/set-rich-presence", d)
                            }
                            loading={loading}
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
            <div>
                <h2 className="text-lg font-semibold text-white">
                    Rich Presence
                </h2>
                <p className="text-xs text-white/45">
                    {connected
                        ? "Manage your presence"
                        : "Reconnect to continue"}
                </p>
            </div>
            <div className="flex gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.location.href = "/rpc/stackables"}
                    className="gap-2 border-purple-500/25 bg-purple-500/10 text-white/90 hover:border-purple-400/40 hover:bg-purple-500/20"
                >
                    <Layers className="h-4 w-4" />
                    Stackable RPCs
                </Button>
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

interface RichPresenceForm {
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
}

const defaultForm: RichPresenceForm = {
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
}

function RichPanel({
    onSubmit,
    loading,
}: {
    onSubmit: (d: Record<string, string | number>) => void
    loading: boolean
}) {
    const { saveToCloud, syncStatus, isCloudFirst, isLoading } = useCloudSyncManager()
    const isSyncing = isLoading
    const hydratedRef = useRef(false)
    
    const getInitialForm = (): RichPresenceForm => {
        if (typeof window === "undefined") return defaultForm
        
        if (isCloudFirst) {
            console.log("[RICH PRESENCE] Cloud-first mode - checking cloud data...")
            return defaultForm
        }
        
        const saved = localStorage.getItem("rich_presence_form")
        if (saved) {
            try {
                return { ...defaultForm, ...JSON.parse(saved) }
            } catch {
                return defaultForm
            }
        }
        return defaultForm
    }
    
    const [form, setForm] = useState<RichPresenceForm>(getInitialForm())
    const [savedForm, setSavedForm] = useState<RichPresenceForm>(getInitialForm())
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [showDialog, setShowDialog] = useState(false)
    const [lastSynced, setLastSynced] = useState<Date | null>(null)

    useEffect(() => {
        setForm(savedForm)
    }, [savedForm])

    const updateForm = useCallback((newForm: RichPresenceForm | ((prev: RichPresenceForm) => RichPresenceForm)) => {
        const updatedForm = typeof newForm === 'function' ? newForm(savedForm) : newForm
        const currentData = JSON.stringify(savedForm)
        const newData = JSON.stringify(updatedForm)
        const hasChanges = currentData !== newData
        setHasUnsavedChanges(hasChanges)
        setSavedForm(updatedForm)
    }, [savedForm])

    const save = useCallback(async () => {
        if (!hasUnsavedChanges) return

        setIsSaving(true)
        try {
            localStorage.setItem("rich_presence_form", JSON.stringify(savedForm))

            console.log("[RICH PRESENCE] Saving to cloud via cloud sync manager...")
            const success = await saveToCloud({
                custom_rpc_settings: savedForm as unknown as Record<string, unknown>,
            })
            
            if (success) {
                console.log("[RICH PRESENCE] Saved to cloud successfully")
                toast.success("Rich Presence settings saved to cloud")
                setHasUnsavedChanges(false)
                setLastSynced(new Date())
            } else {
                console.log("[RICH PRESENCE] Failed to save to cloud")
                toast.error("Failed to save to cloud")
            }
        } catch (error) {
            console.error("Save failed:", error)
            toast.error("Failed to save changes")
        } finally {
            setIsSaving(false)
        }
    }, [hasUnsavedChanges, savedForm, saveToCloud])

    const confirmNavigation = useCallback(() => {
        setShowDialog(false)
    }, [])

    const cancelNavigation = useCallback(() => {
        setShowDialog(false)
    }, [])

    const router = useRouter()

    const { showDialog: showNavigationDialog, onConfirm: handleNavigationConfirm, onCancel: handleNavigationCancel } = useNavigationProtection({
        hasUnsavedChanges,
        onConfirmNavigation: () => {
            console.log("🔒 [RICH] Navigation confirmed")
            confirmNavigation()
        },
        onCancelNavigation: () => {
            console.log("🔒 [RICH] Navigation cancelled")
            cancelNavigation()
        },
    })

    const loadCloudData = useCallback(async () => {
        try {
            const response = await fetch("/api/user/settings")
            if (response.ok) {
                const data = await response.json()
                const cloudSettings = data.settings
                const cloudRpcSettings = cloudSettings?.custom_rpc_settings as RichPresenceForm
                
                if (cloudRpcSettings) {
                    console.log("[RICH PRESENCE] Loaded cloud data:", cloudRpcSettings)
                    
                    if (JSON.stringify(cloudRpcSettings) !== JSON.stringify(savedForm)) {
                        setSavedForm(cloudRpcSettings)
                        setHasUnsavedChanges(false)
                        localStorage.removeItem("rich_presence_form")
                        console.log("[RICH PRESENCE] Cleared local storage for cloud-first mode")
                        toast.success("Rich Presence settings loaded from cloud")
                    }
                } else {
                    console.log("[RICH PRESENCE] No cloud data found, using defaults")
                }
            }
        } catch (error) {
            console.error("[RICH PRESENCE] Error loading cloud data:", error)
            toast.error("Failed to load settings from cloud")
        }
    }, [savedForm])

    useEffect(() => {
        if (isCloudFirst && syncStatus === "synced" && !hydratedRef.current) {
            console.log("[RICH PRESENCE] Loading cloud data in cloud-first mode...")
            loadCloudData()
            hydratedRef.current = true
        }
    }, [isCloudFirst, syncStatus, loadCloudData])

    const activityTypes = [
        { value: "Competing", label: "Competing" },
        { value: "Listening", label: "Listening" },
        { value: "Playing", label: "Playing" },
        { value: "Streaming", label: "Streaming" },
        { value: "Watching", label: "Watching" },
    ].sort((a, b) => a.label.localeCompare(b.label))

    const [platforms, setPlatforms] = useState<Array<{ value: string; label: string }>>([])

    useEffect(() => {
        if (hydratedRef.current) return
        hydratedRef.current = true
        
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
        
        const run = async () => {
            await fetchPlatforms()
        }
        void run()
    }, [])

    const set = (k: keyof RichPresenceForm, v: string) => {
        updateForm((prev: RichPresenceForm) => ({ ...prev, [k]: v }))
    }

    const startMs = form.start ? parseInt(form.start) : NaN
    const endMs = form.end ? parseInt(form.end) : NaN
    const now = Date.now()
    const duration = (ms: number) => {
        if (!Number.isFinite(ms) || ms < 0) return null
        const totalSeconds = Math.floor(ms / 1000)
        const hours = Math.floor(totalSeconds / 3600)
        const minutes = Math.floor((totalSeconds % 3600) / 60)
        const seconds = totalSeconds % 60
        if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}` 
        return `${minutes}:${String(seconds).padStart(2, "0")}` 
    }

    const formatDuration = (ms: number) => {
        if (!Number.isFinite(ms)) return "—"
        if (ms < 0) return "—"
        if (ms === 0) return "0:00"
        return duration(ms) || "—"
    }

    const handleSave = async () => {
        await save()
        
        await fetch("/api/presence-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rich: form }),
        }).catch(() => null)

        const data: Record<string, string | number> = {
            type: form.type || "",
            name: form.name || "Custom Status",
        }
        if (form.details) data.details = form.details
        if (form.state) data.state = form.state
        if (form.streaming_url) data.streaming_url = form.streaming_url
        if (form.platform) data.platform = form.platform
        if (form.large_image_url) data.large_image_url = form.large_image_url
        if (form.large_text) data.large_text = form.large_text
        if (form.small_image_url) data.small_image_url = form.small_image_url
        if (form.small_text) data.small_text = form.small_text
        if (form.start) data.start = parseInt(form.start)
        if (form.end) data.end = parseInt(form.end)
        if (form.button1_label) data.button1_label = form.button1_label
        if (form.button1_url) data.button1_url = form.button1_url
        if (form.button2_label) data.button2_label = form.button2_label
        if (form.button2_url) data.button2_url = form.button2_url
        
        await onSubmit(data)
    }

    return (
        <div className="rounded-xl border border-white/10 bg-black/35 p-6 backdrop-blur-sm">
            <h3 className="mb-6 flex items-center gap-2 text-base font-medium text-white">
                <Gamepad2 className="h-4 w-4 text-[#47a6ff]" />
                Configure Rich Presence
            </h3>
            
            <form
                onSubmit={(e) => {
                    e.preventDefault()
                    void handleSave()
                }}
                className="space-y-4"
            >
                <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                        <Label htmlFor="type" className="text-white/80">Activity Type</Label>
                        <select
                            id="type"
                            value={form.type || ""}
                            onChange={(e) => set("type", e.target.value)}
                            className="w-full mt-1 rounded-lg border border-white/10 bg-black px-3 py-2 text-white hover:bg-sky-900 hover:border-sky-500 transition-colors"
                            disabled={loading || isSyncing}
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
                            value={form.platform || ""}
                            onChange={(e) => set("platform", e.target.value)}
                            className="w-full mt-1 rounded-lg border border-white/10 bg-black px-3 py-2 text-white hover:bg-sky-900 hover:border-sky-500 transition-colors"
                            disabled={loading || isSyncing}
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
                        value={form.streaming_url}
                        onChange={(v) => set("streaming_url", v)}
                        placeholder="https://www.twitch.tv/username"
                        type={(form.type === "Streaming" || form.type === "Watching") ? "text" : "hidden"}
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Activity Name"
                        id="name"
                        value={form.name}
                        onChange={(v) => set("name", v)}
                        placeholder="Game Name"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Details"
                        id="details"
                        value={form.details}
                        onChange={(v) => set("details", v)}
                        placeholder="Playing Game"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="State"
                        id="state"
                        value={form.state}
                        onChange={(v) => set("state", v)}
                        placeholder="In Match"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Large Image URL"
                        id="large_image_url"
                        value={form.large_image_url}
                        onChange={(v) => set("large_image_url", v)}
                        placeholder="https://..."
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Large Image Text"
                        id="large_text"
                        value={form.large_text}
                        onChange={(v) => set("large_text", v)}
                        placeholder="Tooltip"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Small Image URL"
                        id="small_image_url"
                        value={form.small_image_url}
                        onChange={(v) => set("small_image_url", v)}
                        placeholder="https://..."
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Small Image Text"
                        id="small_text"
                        value={form.small_text}
                        onChange={(v) => set("small_text", v)}
                        placeholder="Tooltip"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Start (ms)"
                        id="start"
                        value={form.start}
                        onChange={(v) => set("start", v)}
                        placeholder="1700000000000"
                        type="number"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="End (ms)"
                        id="end"
                        value={form.end}
                        onChange={(v) => set("end", v)}
                        placeholder="1700003600000"
                        type="number"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Button 1 Label"
                        id="button1_label"
                        value={form.button1_label}
                        onChange={(v) => set("button1_label", v)}
                        placeholder="Play Now"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Button 1 URL"
                        id="button1_url"
                        value={form.button1_url}
                        onChange={(v) => set("button1_url", v)}
                        placeholder="https://..."
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Button 2 Label"
                        id="button2_label"
                        value={form.button2_label}
                        onChange={(v) => set("button2_label", v)}
                        placeholder="Join Party"
                        disabled={loading || isSyncing}
                    />
                    <Field
                        label="Button 2 URL"
                        id="button2_url"
                        value={form.button2_url}
                        onChange={(v) => set("button2_url", v)}
                        placeholder="https://..."
                        disabled={loading || isSyncing}
                    />
                </div>
                
                <div className="mt-6 rounded-lg border border-white/15 bg-[#111318]/80 p-4 backdrop-blur-sm">
                    <h4 className="mb-3 text-xs font-medium tracking-wider text-white/55 uppercase">
                        Preview
                    </h4>

                    <div className="flex flex-col gap-4 sm:flex-row">
                        <div className="flex items-start gap-4">
                            <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-white/5">
                                {form.large_image_url ? (
                                    <img
                                        src={form.large_image_url}
                                        alt="Large asset"
                                        className="h-full w-full object-cover"
                                    />
                                ) : (
                                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-slate-700/50 to-slate-900/60">
                                        <Gamepad2 className="h-7 w-7 text-white/70" />
                                    </div>
                                )}

                                {form.small_image_url && (
                                    <div className="absolute -bottom-2 -right-2 h-9 w-9 overflow-hidden rounded-full border-2 border-[#111318] bg-white/10">
                                        <img
                                            src={form.small_image_url}
                                            alt="Small asset"
                                            className="h-full w-full object-cover"
                                        />
                                    </div>
                                )}
                            </div>

                            <div className="min-w-0">
                                <div className="text-[11px] font-semibold tracking-wider text-white/60">
                                    {form.type.toUpperCase()}
                                </div>
                                <div className="mt-1 truncate text-sm font-semibold text-white">
                                    {form.name || "Activity Name"}
                                </div>
                                <div className="mt-1 truncate text-sm text-white/80">
                                    {form.details || "Details"}
                                </div>
                                <div className="mt-0.5 truncate text-sm text-white/70">
                                    {form.state || "State"}
                                </div>

                                {(form.large_text || form.small_text) && (
                                    <div className="mt-2 text-xs text-white/45">
                                        {form.large_text && (
                                            <div className="truncate">{form.large_text}</div>
                                        )}
                                        {form.small_text && (
                                            <div className="truncate">{form.small_text}</div>
                                        )}
                                    </div>
                                )}

                                {(Number.isFinite(startMs) || Number.isFinite(endMs)) && (
                                    <div className="mt-2 text-xs text-white/45">
                                        {Number.isFinite(startMs) && startMs > 0 && (
                                            <div>
                                                Elapsed: {formatDuration(now - startMs)}
                                            </div>
                                        )}
                                        {Number.isFinite(endMs) && endMs > 0 && (
                                            <div>
                                                Remaining: {formatDuration(endMs - now)}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>

                        {(form.button1_label || form.button2_label) && (
                            <div className="flex shrink-0 flex-col gap-2 sm:ml-auto sm:items-end">
                                {form.button1_label && (
                                    <button
                                        type="button"
                                        className="w-full rounded-md bg-[#5865F2] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#4752C4] sm:w-auto"
                                    >
                                        {form.button1_label}
                                    </button>
                                )}
                                {form.button2_label && (
                                    <button
                                        type="button"
                                        className="w-full rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm font-medium text-white/90 transition-colors hover:bg-white/10 sm:w-auto"
                                    >
                                        {form.button2_label}
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                <SaveChanges
                    show={hasUnsavedChanges}
                    saving={isSaving}
                    onSave={save}
                    isSyncing={isSyncing}
                    lastSynced={lastSynced}
                />

                <div className="mt-6 flex gap-3">
                    <Button
                        type="submit"
                        disabled={loading || !form.name || isSyncing || hasUnsavedChanges}
                        className="flex-1 gap-2 rounded-lg border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                    >
                        {loading || isSyncing ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Check className="h-4 w-4" />
                        )}
                        {hasUnsavedChanges ? "Save changes first" : isSyncing ? "Syncing..." : "Set Rich Presence"}
                    </Button>
                </div>
            </form>

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
        </div>
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
                className="border-white/20 bg-white/5 text-white placeholder:text-white/35"
            />
        </div>
    )
}
