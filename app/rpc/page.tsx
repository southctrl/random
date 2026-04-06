"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { useCrossDeviceSync } from "@/hooks/use-cross-device-sync"
import { useDiscordToken } from "@/hooks/use-local-storage"
import { BrandedBackground } from "@/components/branded-background"
import { RpcUnreachableOverlay } from "@/components/rpc-unreachable-overlay"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { useCloudSyncManager } from "@/hooks/use-cloud-sync-manager"
import {
    Gamepad2,
    Music,
    Sparkles,
    LogOut,
    RefreshCw,
    Circle,
    Loader2,
    User,
    Wifi,
    WifiOff,
    Settings,
    ChevronDown,
    ChevronRight,
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

const statusMeta: Record<
    Status,
    { label: string; color: string; icon: Status }
> = {
    online: { label: "Online", color: "text-green-400", icon: "online" },
    idle: { label: "Idle", color: "text-yellow-400", icon: "idle" },
    dnd: { label: "Do Not Disturb", color: "text-red-400", icon: "dnd" },
    invisible: {
        label: "Invisible",
        color: "text-gray-400",
        icon: "invisible",
    },
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

export default function RpcPage() {
    const router = useRouter()
    const { data: sessionAuth, isPending: sessionPending } =
        authClient.useSession()
    const [loading, setLoading] = useState(false)
    const [discordToken, setDiscordToken] = useDiscordToken()
    const [currentStatus, setCurrentStatus] = useState<CurrentStatus | null>(
        null
    )
    const [refreshing, setRefreshing] = useState(false)
    const [connected, setConnected] = useState(false)
    const [rpcUnreachable, setRpcUnreachable] = useState(false)
    const [rpcRetrying, setRpcRetrying] = useState(false)
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(() => {
        if (typeof window === "undefined") return new Set(["RPC"])
        
        if (syncStatus === "synced") {
            console.log("[MAIN RPC] Cloud-first mode - will load expanded categories from cloud...")
            return new Set(["RPC"])
        }
        
        const saved = localStorage.getItem("expanded_categories")
        if (saved) {
            try {
                return new Set(JSON.parse(saved))
            } catch {
                return new Set(["RPC"])
            }
        }
        return new Set(["RPC"])
    })
    const [connectionAttempts, setConnectionAttempts] = useState(0)
    const [connectionError, setConnectionError] = useState<string | null>(null)
    const [isConnecting, setIsConnecting] = useState(false)

    const { saveToCloud, syncStatus, isCloudFirst, isLoading } = useCloudSyncManager()
    const hydratedRef = useRef(false)

    const {
        isAuthenticated,
        isLoading: syncLoading,
        hasCloudToken,
        hasLocalToken,
        syncFromCloud,
        syncToCloud,
        user
    } = useCrossDeviceSync()

    useEffect(() => {
        if (sessionPending) return
        const init = async () => {
            console.log("🚀 [RPC PAGE] Initializing RPC page...")
            if (!sessionAuth?.session) {
                console.log("[RPC PAGE] No session found, redirecting to login")
                router.push("/login")
                return
            }
            if (!discordToken) {
                console.log("[RPC PAGE] No Discord token found, redirecting to onboarding")
                router.push("/onboarding")
                return
            }
            
            console.log("🔌 [RPC PAGE] Discord token found (first 20 chars):", discordToken.substring(0, 20) + "...")
            const { unreachable, data } = await fetchStatus(discordToken)
            setRpcUnreachable(unreachable)
            setCurrentStatus(data)
            const isConnected = !unreachable && data !== null
            setConnected(isConnected)
            console.log("📡 [RPC PAGE] Initial connection status:", isConnected ? "Connected" : "Disconnected")
            
            if (!isConnected) {
                handleConnect()
            }
        }
        init()
    }, [router, sessionAuth, sessionPending, discordToken])

    const refresh = async () => {
        if (!discordToken) return
        setRefreshing(true)
        const { unreachable, data } = await fetchStatus(discordToken)
        console.log("Refresh data:", data)
        setRpcUnreachable(unreachable)
        setCurrentStatus(data)
        setConnected(!unreachable && data !== null)
        setTimeout(() => setRefreshing(false), 300)
    }

    const retryRpcConnection = async () => {
        if (!discordToken) return
        setRpcRetrying(true)
        await refresh()
        setRpcRetrying(false)
    }

    useEffect(() => {
        if (!rpcUnreachable || !discordToken) return
        const id = setInterval(async () => {
            const { unreachable, data } = await fetchStatus(discordToken)
            setRpcUnreachable(unreachable)
            setCurrentStatus(data)
            setConnected(!unreachable && data !== null)
        }, 4000)
        return () => clearInterval(id)
    }, [rpcUnreachable, discordToken])

    const notify = (type: "success" | "error", msg: string) => {
        if (type === "success") toast.success(msg)
        else toast.error(msg)
    }

    const signOut = async () => {
        await authClient.signOut()
        router.push("/login")
    }

    const api = async (endpoint: string, body?: object, verb = "POST") => {
        if (!discordToken) return null
        setLoading(true)
        try {
            const res = await fetch(`${API_BASE}/${endpoint}`, {
                method: verb,
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${discordToken}`,
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
        if (!discordToken) return
        
        setIsConnecting(true)
        let attempts = 0
        const maxAttempts = 5
        
        while (attempts < maxAttempts) {
            try {
                const res = await fetch(`${API_BASE}/login`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${discordToken}`,
                    },
                    body: JSON.stringify({ token: discordToken }),
                })
                
                if (res.ok) {
                    const { unreachable, data } = await fetchStatus(discordToken)
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

    // Load cloud data if in cloud-first mode
    useEffect(() => {
        if (isCloudFirst && syncStatus === "synced" && !hydratedRef.current) {
            console.log("[MAIN RPC] Loading cloud data in cloud-first mode...")
            loadCloudData()
            hydratedRef.current = true
        }
    }, [isCloudFirst, syncStatus, hydratedRef])

    const loadCloudData = useCallback(async () => {
        try {
            const response = await fetch("/api/user/settings")
            if (response.ok) {
                const data = await response.json()
                const cloudSettings = data.settings
                const cloudExpandedCategories = cloudSettings?.custom_rpc_settings?.expandedCategories as string[]
                
                if (cloudExpandedCategories) {
                    console.log("✅ [MAIN RPC] Loaded cloud expanded categories:", cloudExpandedCategories)
                    setExpandedCategories(new Set(cloudExpandedCategories))
                    
                    localStorage.removeItem("expanded_categories")
                    console.log("🗑️ [MAIN RPC] Cleared local storage for cloud-first mode")
                    toast.success("RPC settings loaded from cloud")
                } else {
                    console.log("ℹ️ [MAIN RPC] No cloud expanded categories found, using defaults")
                }
            }
        } catch (error) {
            console.error("[MAIN RPC] Error loading cloud data:", error)
            toast.error("Failed to load RPC settings from cloud")
        }
    }, [])

    // Save to cloud when categories change
    useEffect(() => {
        if (isCloudFirst) {
            saveToCloud({
                custom_rpc_settings: { 
                    expandedCategories: Array.from(expandedCategories)
                } as Record<string, unknown>,
            })
        } else {
            localStorage.setItem("expanded_categories", JSON.stringify(Array.from(expandedCategories)))
        }
    }, [expandedCategories, isCloudFirst, saveToCloud])

    const getConnectButtonText = () => {
        if (isConnecting) return "Connecting..."
        if (syncLoading) return "Syncing..."
        if (connected) return "Connected"
        if (hasCloudToken) return "Connect with Cloud Token"
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
            <Sidebar
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
                expandedCategories={expandedCategories}
                onToggleCategory={toggleCategory}
                userName={sessionAuth?.user?.name || "User"}
                onConnect={handleConnect}
                isConnecting={isConnecting}
                getConnectButtonText={getConnectButtonText}
                syncStatus={syncStatus}
                syncLoading={syncLoading}
                hasCloudToken={hasCloudToken}
                hasLocalToken={hasLocalToken}
                syncToCloud={syncToCloud}
                syncFromCloud={syncFromCloud}
            />

            <div className="flex flex-1 flex-col">
                <main className="flex-1 px-4 py-8 sm:px-6 lg:px-10">
                    <div className="mx-auto w-full max-w-6xl">
                        <div className="text-center py-20">
                            <h1 className="text-4xl font-bold text-white mb-4">
                                Welcome, {sessionAuth?.user?.name || "User"}!
                            </h1>
                            <p className="text-lg text-white/60">
                                Select an option from the category to get started
                            </p>
                        </div>
                    </div>
                </main>
            </div>
            </div>
        </div>
    )
}

function Sidebar({
    onSignOut,
    connected,
    status,
    avatarUrl,
    expandedCategories,
    onToggleCategory,
    userName,
    onConnect,
    isConnecting,
    getConnectButtonText,
    syncStatus,
    syncLoading,
    hasCloudToken,
    hasLocalToken,
    syncToCloud,
    syncFromCloud,
}: {
    onSignOut: () => void
    connected: boolean
    status: Status
    avatarUrl: string | null
    expandedCategories: Set<string>
    onToggleCategory: (category: string) => void
    userName: string
    onConnect: () => void
    isConnecting: boolean
    getConnectButtonText: () => string
    syncStatus: "synced" | "syncing" | "out-of-sync" | "no-token"
    syncLoading: boolean
    hasCloudToken: boolean
    hasLocalToken: boolean
    syncToCloud: () => Promise<boolean>
    syncFromCloud: () => Promise<boolean>
}) {
    return (
        <aside className="flex min-h-screen w-60 flex-col border-r border-white/10 bg-black/25 backdrop-blur-sm">
            <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-white/10 px-5">
                {avatarUrl ? (
                    <div className="relative h-9 w-9 shrink-0">
                        <img
                            src={avatarUrl}
                            alt=""
                            width={36}
                            height={36}
                            className="h-9 w-9 rounded-full object-cover ring-1 ring-white/20"
                            referrerPolicy="no-referrer"
                        />
                        <span className="absolute -bottom-0.5 -right-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-[#0b0f17] ring-2 ring-[#0b0f17]">
                            <StatusDot status={status} className="h-3 w-3" />
                        </span>
                    </div>
                ) : (
                    <div className="relative h-9 w-9 shrink-0" aria-hidden>
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/[0.08] ring-1 ring-white/15">
                            <User className="h-5 w-5 text-white/40" />
                        </div>
                        <span className="absolute -bottom-0.5 -right-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-[#0b0f17] ring-2 ring-[#0b0f17]">
                            <StatusDot status={status} className="h-3 w-3" />
                        </span>
                    </div>
                )}
                <div>
                    <h1 className="text-sm font-semibold text-white">Welcome, {userName}!</h1>
                    <p className="text-xs text-white/45">Expel Selfbot</p>
                </div>
            </div>

            <nav className="flex-1 space-y-2 overflow-y-auto p-3">
                {navItems.map((category) => (
                    <div key={category.category}>
                        <button
                            onClick={() => onToggleCategory(category.category)}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white/80 hover:bg-white/5 transition-colors"
                        >
                            {expandedCategories.has(category.category) ? (
                                <ChevronDown className="h-4 w-4" />
                            ) : (
                                <ChevronRight className="h-4 w-4" />
                            )}
                            {category.category}
                        </button>
                        
                        {expandedCategories.has(category.category) && (
                            <div className="ml-4 mt-1 space-y-1">
                                {category.items.map((item) => (
                                    <Link
                                        key={item.id}
                                        href={`/rpc/${item.id}`}
                                        className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors text-white/50 hover:bg-white/5 hover:text-white/90"
                                    >
                                        <Icon name={item.icon} />
                                        {item.label}
                                    </Link>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </nav>

            <div className="shrink-0 border-t border-white/10 bg-black/20 p-3 space-y-3">
                <div className="flex items-center gap-2 px-1 text-xs text-white/45">
                    {syncStatus === "synced" ? (
                        <>
                            <Wifi className="h-3 w-3 shrink-0 text-green-500" />
                            Cloud Synced
                        </>
                    ) : syncStatus === "syncing" ? (
                        <>
                            <RefreshCw className="h-3 w-3 shrink-0 animate-spin text-blue-500" />
                            Syncing...
                        </>
                    ) : syncStatus === "out-of-sync" ? (
                        <>
                            <WifiOff className="h-3 w-3 shrink-0 text-yellow-500" />
                            Out of Sync
                        </>
                    ) : (
                        <>
                            <WifiOff className="h-3 w-3 shrink-0 text-gray-500" />
                            No Cloud Data
                        </>
                    )}
                </div>

                {syncStatus === "out-of-sync" && hasLocalToken && (
                    <Button
                        variant="outline"
                        onClick={() => syncToCloud()}
                        disabled={syncLoading}
                        className="w-full justify-start gap-2 rounded-xl border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20 text-xs px-2 py-1.5 h-auto"
                    >
                        {syncLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                            <RefreshCw className="h-3 w-3" />
                        )}
                        Sync to Cloud
                    </Button>
                )}

                {syncStatus === "out-of-sync" && hasCloudToken && !hasLocalToken && (
                    <Button
                        variant="outline"
                        onClick={() => syncFromCloud()}
                        disabled={syncLoading}
                        className="w-full justify-start gap-2 rounded-xl border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20 text-xs px-2 py-1.5 h-auto"
                    >
                        {syncLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                            <RefreshCw className="h-3 w-3" />
                        )}
                        Sync from Cloud
                    </Button>
                )}

                <div className="flex items-center gap-2 px-1 text-xs text-white/45">
                    {connected ? (
                        <>
                            <Wifi className="h-3 w-3 shrink-0 text-green-500" />
                            Connected
                        </>
                    ) : (
                        <>
                            <WifiOff className="h-3 w-3 shrink-0 text-red-500" />
                            Disconnected
                        </>
                    )}
                </div>
                {!connected && (
                    <Button
                        variant="outline"
                        onClick={onConnect}
                        disabled={isConnecting}
                        className="mb-2 w-full justify-start gap-3 rounded-xl border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                    >
                        {isConnecting ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <RefreshCw className="h-4 w-4" />
                        )}
                        {getConnectButtonText()}
                    </Button>
                )}
                <Button
                    variant="ghost"
                    onClick={onSignOut}
                    className="mb-2 w-full justify-start gap-3 rounded-xl border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                </Button>
                <Link
                    href="/dashboard/settings"
                    className="flex w-full items-center gap-3 rounded-xl border-sky-500/25 bg-sky-500/10 px-3 py-2.5 text-sm text-white/90 shadow-[0_0_20px_-8px_rgba(71,166,255,0.5)] transition-colors hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    <Settings className="h-4 w-4 shrink-0 text-[#7ec8ff]" />
                    <span className="font-medium">Settings</span>
                </Link>
            </div>
        </aside>
    )
}
