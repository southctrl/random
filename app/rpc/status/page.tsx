"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { BrandedBackground } from "@/components/branded-background"
import { RpcUnreachableOverlay } from "@/components/rpc-unreachable-overlay"
import { RpcSidebar } from "@/components/layout/rpc-sidebar"
import { MobileHeader } from "@/components/layout/mobile-sidebar"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { useAutoSave } from "@/hooks/use-auto-save"
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

export default function StatusPage() {
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
    const [connectionAttempts, setConnectionAttempts] = useState(0)
    const [connectionError, setConnectionError] = useState<string | null>(null)
    const [isConnecting, setIsConnecting] = useState(false)

    const { isSyncing } = useCloudSettings()
    const { saveToCloud, syncStatus, isCloudFirst, isLoading } = useCloudSyncManager()
    const hydratedRef = useRef(false)

    useNavigationProtection({
        hasUnsavedChanges: false,
    })

    const [selectedStatus, setSelectedStatus] = useState<Status | undefined>(() => {
        if (typeof window === "undefined") return undefined
        
        if (isCloudFirst) {
            console.log("[STATUS] Cloud-first mode - will load selected status from cloud...")
            return undefined
        }
        
        const saved = localStorage.getItem("selected_status")
        if (saved) {
            try {
                return JSON.parse(saved) as Status
            } catch {
                return undefined
            }
        }
        return undefined
    })

    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(() => {
        if (typeof window === "undefined") return new Set(["RPC"])
        
        if (isCloudFirst) {
            console.log("[STATUS] Cloud-first mode - will load expanded categories from cloud...")
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
            setSelectedStatus(data?.status as Status || undefined)
            
            if (!isConnected) {
                handleConnect()
            }
            
            if (isCloudFirst && syncStatus === "synced" && !hydratedRef.current) {
                console.log("[STATUS] Loading cloud data in cloud-first mode...")
                loadCloudData()
                hydratedRef.current = true
            }
        }
        init()
    }, [router, sessionAuth, sessionPending, validateToken, isCloudFirst, syncStatus, hydratedRef])

    const loadCloudData = useCallback(async () => {
        try {
            const response = await fetch("/api/user/settings")
            if (response.ok) {
                const data = await response.json()
                const cloudSettings = data.settings
                const cloudSelectedStatus = cloudSettings?.custom_rpc_settings?.selectedStatus as Status
                const cloudExpandedCategories = cloudSettings?.custom_rpc_settings?.expandedCategories as string[]
                
                if (cloudSelectedStatus) {
                    console.log("[STATUS] Loaded cloud status:", cloudSelectedStatus)
                    setSelectedStatus(cloudSelectedStatus)
                }
                
                if (cloudExpandedCategories) {
                    console.log("[STATUS] Loaded cloud expanded categories:", cloudExpandedCategories)
                    setExpandedCategories(new Set(cloudExpandedCategories))
                }
                
                if (cloudSelectedStatus || cloudExpandedCategories) {
                    localStorage.removeItem("selected_status")
                    localStorage.removeItem("expanded_categories")
                    console.log("[STATUS] Cleared local storage for cloud-first mode")
                    toast.success("Status settings loaded from cloud")
                }
            }
        } catch (error) {
            console.error("[STATUS] Error loading cloud data:", error)
            toast.error("Failed to load status settings from cloud")
        }
    }, [])

    useEffect(() => {
        if (selectedStatus) {
            if (isCloudFirst) {
                saveToCloud({
                    custom_rpc_settings: { 
                        selectedStatus: selectedStatus,
                        expandedCategories: Array.from(expandedCategories)
                    } as Record<string, unknown>,
                })
            } else {
                localStorage.setItem("selected_status", JSON.stringify(selectedStatus))
            }
        }
    }, [selectedStatus, expandedCategories, isCloudFirst, saveToCloud])

    useEffect(() => {
        if (isCloudFirst) {
            saveToCloud({
                custom_rpc_settings: { 
                    selectedStatus: selectedStatus,
                    expandedCategories: Array.from(expandedCategories)
                } as Record<string, unknown>,
            })
        } else {
            localStorage.setItem("expanded_categories", JSON.stringify(Array.from(expandedCategories)))
        }
    }, [expandedCategories, isCloudFirst, saveToCloud, selectedStatus])

    const refresh = async () => {
        if (!token) return
        setRefreshing(true)
        const { unreachable, data } = await fetchStatus(token)
        console.log("Refresh data:", data)
        setRpcUnreachable(unreachable)
        setCurrentStatus(data)
        setSelectedStatus(data?.status as Status || undefined)
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
                    title="Status" 
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
                        <StatusPanel
                            onSelect={(s) => {
                                setSelectedStatus(s)
                                api("status/update", { status: s })
                            }}
                            loading={loading}
                            currentStatus={selectedStatus}
                        />
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
                                        className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                                            item.id === "status"
                                                ? "border border-sky-500/30 bg-sky-500/10 text-[#7ec8ff]"
                                                : "text-white/50 hover:bg-white/5 hover:text-white/90"
                                        }`}
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

            <div className="shrink-0 border-t border-white/10 bg-black/20 p-3">
                <div className="mb-3 flex items-center gap-2 px-1 text-xs text-white/45">
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
        <header className="flex h-16 items-center justify-between border-b border-white/10 bg-black/20 px-6 backdrop-blur-sm">
            <div>
                <h2 className="text-lg font-semibold text-white">
                    Status
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

function StatusPanel({
    onSelect,
    loading,
    currentStatus,
}: {
    onSelect: (s: Status) => void
    loading: boolean
    currentStatus?: Status
}) {
    const statuses: Status[] = ["online", "idle", "dnd", "invisible"]

    return (
        <div className="rounded-xl border border-white/10 bg-black/35 p-6 backdrop-blur-sm">
            <h3 className="mb-6 flex items-center gap-2 text-base font-medium text-white">
                <Circle className="h-4 w-4 text-[#47a6ff]" />
                Set Status
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
                {statuses.map((s) => (
                    <button
                        key={s}
                        onClick={() => onSelect(s)}
                        disabled={loading}
                        className={`flex items-center gap-3 rounded-lg border bg-white/5 p-4 text-left transition-all hover:border-white/25 disabled:opacity-50 ${
                            currentStatus === s
                                ? "border-[#47a6ff]/50 bg-sky-500/10"
                                : "border-white/10"
                        }`}
                    >
                        <StatusDot status={s} className="h-5 w-5" />
                        <div>
                            <p className="text-sm font-medium text-white">
                                {statusMeta[s].label}
                            </p>
                            <p className="text-xs text-white/45">/ {s}</p>
                        </div>
                    </button>
                ))}
            </div>
        </div>
    )
}
