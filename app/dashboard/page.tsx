"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { BrandedBackground } from "@/components/branded-background"
import { RpcUnreachableOverlay } from "@/components/rpc-unreachable-overlay"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { SaveChanges } from "@/components/layout/SaveChanges"
import { UnsavedChangesDialog } from "@/components/layout/UnsavedChangesDialog"
import { useAutoSave } from "@/hooks/use-auto-save"
import { toast } from "sonner"
import {
    Gamepad2,
    Music,
    Sparkles,
    LogOut,
    RefreshCw,
    Trash2,
    Circle,
    Moon,
    Bell,
    Eye,
    Check,
    Loader2,
    User,
    Wifi,
    WifiOff,
    Settings,
    ChevronDown,
    ChevronRight,
    Cloud,
    CloudOff,
} from "lucide-react"
import { useCloudSettings } from "@/hooks/use-cloud-settings"
import { MobileSidebar, MobileHeader } from "@/components/layout/mobile-sidebar"

const API_BASE = "/api/rpc"

type Status = "online" | "idle" | "dnd" | "invisible"
type Tab = "status" | "rich" | "custom" | "spotify"

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
        href: "/rpc",
        items: [
            { id: "status" as Tab, label: "Status", icon: "status" },
            { id: "custom" as Tab, label: "Custom Status", icon: "custom" },
            { id: "rich" as Tab, label: "Rich Presence", icon: "rich" },
            { id: "spotify" as Tab, label: "Spotify Lyrics", icon: "spotify" },
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

export default function DashboardPage() {
    const router = useRouter()
    const { data: sessionAuth, isPending: sessionPending } =
        authClient.useSession()
    const [loading, setLoading] = useState(false)
    const [token, setToken] = useState<string | null>(null)
    const [currentStatus, setCurrentStatus] = useState<CurrentStatus | null>(
        null
    )
    const [selectedStatus, setSelectedStatus] = useState<Status | undefined>(undefined)
    const [activeTab, setActiveTab] = useState<Tab | null>(null)
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
    }, [router, sessionAuth, sessionPending, validateToken])

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

    const handleLogin = () => api("login", { token })
    const handleClear = () => api("clear")

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
            {/* Mobile Sidebar */}
            <MobileSidebar
                navItems={navItems}
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
                onSignOut={signOut}
            />

            {/* Desktop Sidebar - hidden on mobile */}
            <Sidebar
                activeTab={activeTab}
                onTabChange={setActiveTab}
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
            />

            <div className="flex flex-1 flex-col">
                {activeTab && (
                    <TopBar
                        title={activeTab}
                        onRefresh={refresh}
                        onClear={handleClear}
                        refreshing={refreshing}
                        loading={loading}
                        connected={connected}
                    />
                )}

                <main className="flex-1 px-4 py-8 pt-20 md:pt-8 sm:px-6 lg:px-10">
                    <div className="mx-auto w-full max-w-6xl">
                        <div className="text-center py-20">
                            <h1 className="text-4xl font-bold text-white mb-4">
                                Welcome, {sessionAuth?.user?.name || "User"}!
                            </h1>
                            <p className="text-lg text-white/60">
                                Select an option from the sidebar to get started
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
    activeTab,
    onTabChange,
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
    activeTab: Tab | null
    onTabChange: (t: Tab | null) => void
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
        <aside className="hidden md:flex min-h-screen w-60 flex-col border-r border-white/10 bg-black/25 backdrop-blur-sm">
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
                                        href={`${category.href}/${item.id}`}
                                        className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                                            activeTab === item.id
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
    title,
    onRefresh,
    onClear,
    refreshing,
    loading,
    connected,
}: {
    title: Tab
    onRefresh: () => void
    onClear: () => void
    refreshing: boolean
    loading: boolean
    connected: boolean
}) {
    const labels: Record<Tab, string> = {
        status: "Status",
        rich: "Rich Presence",
        custom: "Custom Status",
        spotify: "Spotify Lyrics",
    }

    return (
        <header className="flex h-16 items-center justify-between border-b border-white/10 bg-black/20 px-6 backdrop-blur-sm">
            <div>
                <h2 className="text-lg font-semibold text-white">
                    {labels[title]}
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

function RichPanel({
    onSubmit,
    loading,
}: {
    onSubmit: (d: Record<string, string | number>) => void
    loading: boolean
}) {
    const [form, setForm] = useState({
        platform: "",
        name: "",
        details: "",
        state: "",
        large_image_url: "",
        large_text: "",
        small_image_url: "",
        small_text: "",
        start: "",
        end: "",
        button1_label: "",
        button1_url: "",
        button2_label: "",
        button2_url: "",
    })

    const hydratedRef = useRef(false)
    const [initial, setInitial] = useState(form)
    const [platforms, setPlatforms] = useState<Array<{ value: string; label: string }>>([])
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
    const [saveTimeout, setSaveTimeout] = useState<NodeJS.Timeout | null>(null)
    const [timeRemaining, setTimeRemaining] = useState<number | null>(null)

    useEffect(() => {
        if (hydratedRef.current) return
        hydratedRef.current = true
        
        const fetchPlatforms = async () => {
            try {
                const res = await fetch(`${API_BASE}/platforms`)
                const data = await res.json()
                if (data.platforms) {
                    setPlatforms(data.platforms)
                }
            } catch (error) {
                console.error("Failed to fetch platforms:", error)
            }
        }
        
        const run = async () => {
            await fetchPlatforms()
            
            const res = await fetch("/api/presence-settings")
            const data = (await res.json().catch(() => null)) as
                | { rich?: Record<string, unknown> | null }
                | null
            const rich = data?.rich
            if (!rich || typeof rich !== "object") {
                setInitial(form)
                return
            }
            const next = { ...form }
            for (const k of Object.keys(next)) {
                const v = (rich as Record<string, unknown>)[k]
                if (typeof v === "string") (next as Record<string, string>)[k] = v
            }
            setForm(next)
            setInitial(next)
        }
        void run()
    }, [])

    const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }))

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

    const isDirty = JSON.stringify(form) !== JSON.stringify(initial)

    useEffect(() => {
        if (isDirty && !hasUnsavedChanges) {
            setHasUnsavedChanges(true)
            const timeout = setTimeout(() => {
                toast.warning("Changes not saved! Your changes will be lost if you don't save within 2 minutes.")
                setHasUnsavedChanges(false)
                setTimeRemaining(null)
            }, 120000)
            
            setSaveTimeout(timeout)
            
            let timeLeft = 120
            const countdown = setInterval(() => {
                timeLeft -= 1
                setTimeRemaining(timeLeft)
                if (timeLeft <= 0) {
                    clearInterval(countdown)
                }
            }, 1000)
            
            return () => {
                clearTimeout(timeout)
                clearInterval(countdown)
            }
        } else if (!isDirty && hasUnsavedChanges) {
            if (saveTimeout) {
                clearTimeout(saveTimeout)
                setSaveTimeout(null)
            }
            setHasUnsavedChanges(false)
            setTimeRemaining(null)
        }
    }, [isDirty, hasUnsavedChanges, saveTimeout])

    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (hasUnsavedChanges) {
                e.preventDefault()
                e.returnValue = "You have unsaved changes. Are you sure you want to leave?"
                return "You have unsaved changes. Are you sure you want to leave?"
            }
        }

        window.addEventListener('beforeunload', handleBeforeUnload)
        return () => window.removeEventListener('beforeunload', handleBeforeUnload)
    }, [hasUnsavedChanges])

    const handleSave = async () => {
        await fetch("/api/presence-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rich: form }),
        }).catch(() => null)

        const data: Record<string, string | number> = {
            platform: form.platform,
        }
        if (form.name) data.name = form.name
        if (form.details) data.details = form.details
        if (form.state) data.state = form.state
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
        onSubmit(data)

        setInitial(form)
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
                        <Label htmlFor="platform" className="text-white/80">Platform</Label>
                        <select
                            id="platform"
                            value={form.platform}
                            onChange={(e) => set("platform", e.target.value)}
                            className="w-full mt-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white"
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
                        label="Activity Name"
                        id="name"
                        value={form.name}
                        onChange={(v) => set("name", v)}
                        placeholder="Game Name"
                    />
                    <Field
                        label="Details"
                        id="details"
                        value={form.details}
                        onChange={(v) => set("details", v)}
                        placeholder="Playing Game"
                    />
                    <Field
                        label="State"
                        id="state"
                        value={form.state}
                        onChange={(v) => set("state", v)}
                        placeholder="In Match"
                    />
                    <Field
                        label="Large Image URL"
                        id="large_image_url"
                        value={form.large_image_url}
                        onChange={(v) => set("large_image_url", v)}
                        placeholder="https://..."
                    />
                    <Field
                        label="Large Image Text"
                        id="large_text"
                        value={form.large_text}
                        onChange={(v) => set("large_text", v)}
                        placeholder="Tooltip"
                    />
                    <Field
                        label="Small Image URL"
                        id="small_image_url"
                        value={form.small_image_url}
                        onChange={(v) => set("small_image_url", v)}
                        placeholder="https://..."
                    />
                    <Field
                        label="Small Image Text"
                        id="small_text"
                        value={form.small_text}
                        onChange={(v) => set("small_text", v)}
                        placeholder="Tooltip"
                    />
                    <Field
                        label="Start (ms)"
                        id="start"
                        value={form.start}
                        onChange={(v) => set("start", v)}
                        placeholder="1700000000000"
                        type="number"
                    />
                    <Field
                        label="End (ms)"
                        id="end"
                        value={form.end}
                        onChange={(v) => set("end", v)}
                        placeholder="1700003600000"
                        type="number"
                    />
                    <Field
                        label="Button 1 Label"
                        id="button1_label"
                        value={form.button1_label}
                        onChange={(v) => set("button1_label", v)}
                        placeholder="Play Now"
                    />
                    <Field
                        label="Button 1 URL"
                        id="button1_url"
                        value={form.button1_url}
                        onChange={(v) => set("button1_url", v)}
                        placeholder="https://..."
                    />
                    <Field
                        label="Button 2 Label"
                        id="button2_label"
                        value={form.button2_label}
                        onChange={(v) => set("button2_label", v)}
                        placeholder="Join Party"
                    />
                    <Field
                        label="Button 2 URL"
                        id="button2_url"
                        value={form.button2_url}
                        onChange={(v) => set("button2_url", v)}
                        placeholder="https://..."
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
                                    PLAYING A GAME
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

                <div className="mt-6 flex gap-3">
                    <Button
                        type="submit"
                        disabled={loading || !form.name}
                        className="flex-1 gap-2 rounded-lg border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                    >
                        {loading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Check className="h-4 w-4" />
                        )}
                        Set Rich Presence
                    </Button>
                </div>
            </form>
        </div>
    )
}

function CustomPanel({
    onSubmit,
    loading,
}: {
    onSubmit: (d: { emoji?: string; text?: string }) => void
    loading: boolean
}) {
    const [form, setForm] = useState({ emoji: "", text: "" })

    const handleSubmit = () => {
        if (!form.emoji && !form.text) return
        onSubmit(form)
    }

    return (
        <div className="rounded-xl border border-white/10 bg-black/35 p-6 backdrop-blur-sm">
            <h3 className="mb-6 flex items-center gap-2 text-base font-medium text-white">
                <Sparkles className="h-4 w-4 text-[#47a6ff]" />
                Set Custom Status
            </h3>
            
            <div className="space-y-4">
                <div>
                    <Label htmlFor="emoji" className="text-white/80">Emoji</Label>
                    <Input
                        id="emoji"
                        value={form.emoji}
                        onChange={(e) => setForm((f) => ({ ...f, emoji: e.target.value }))}
                        placeholder="😊"
                        maxLength={2}
                        disabled={loading}
                        className="border-white/10 bg-white/5 text-white"
                    />
                </div>
                
                <div>
                    <Label htmlFor="text" className="text-white/80">Status Text</Label>
                    <Input
                        id="text"
                        value={form.text}
                        onChange={(e) => setForm((f) => ({ ...f, text: e.target.value }))}
                        placeholder="Working on something amazing..."
                        disabled={loading}
                        className="border-white/10 bg-white/5 text-white"
                    />
                </div>

                <Button
                    onClick={handleSubmit}
                    disabled={loading || (!form.emoji && !form.text)}
                    className="w-full gap-2 rounded-lg border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    {loading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Check className="h-4 w-4" />
                    )}
                    Set Custom Status
                </Button>
            </div>
        </div>
    )
}

function SpotifyPanel({
    onSubmit,
    loading,
}: {
    onSubmit: (d: Record<string, unknown>) => void
    loading: boolean
}) {
    return (
        <div className="rounded-xl border border-white/10 bg-black/35 p-6 backdrop-blur-sm">
            <h3 className="mb-6 flex items-center gap-2 text-base font-medium text-white">
                <Music className="h-4 w-4 text-[#47a6ff]" />
                Spotify Lyrics Display
            </h3>
            
            <div className="space-y-4">
                <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <h4 className="font-medium text-white mb-2">Current Song</h4>
                    <p className="text-sm text-white/60">No song playing</p>
                </div>
                
                <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <h4 className="font-medium text-white mb-2">Lyrics</h4>
                    <p className="text-sm text-white/60">Lyrics will appear here</p>
                </div>

                <Button
                    onClick={() => onSubmit({})}
                    disabled={loading}
                    className="w-full gap-2 rounded-lg border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    {loading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Check className="h-4 w-4" />
                    )}
                    Enable Spotify Lyrics
                </Button>
            </div>
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
}: {
    label: string
    id: string
    value: string
    onChange: (v: string) => void
    placeholder: string
    type?: string
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
                className="border-white/20 bg-white/5 text-white placeholder:text-white/35"
            />
        </div>
    )
}
