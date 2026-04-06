"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { BrandedBackground } from "@/components/branded-background"
import { RpcUnreachableOverlay } from "@/components/rpc-unreachable-overlay"
import { RpcSidebar } from "@/components/layout/rpc-sidebar"
import { MobileHeader } from "@/components/layout/mobile-sidebar"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { useCloudSettings } from "@/hooks/use-cloud-settings"
import { useAutoSave } from "@/hooks/use-auto-save"
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
    return <Circle className={`${className} ${colors[status]}}`} />
}

export default function SpotifyPage() {
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
                {/* Mobile Header */}
                <MobileHeader 
                    title="Spotify Lyrics" 
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
                        <div className="relative">
                            <div className="pointer-events-none select-none opacity-40 blur-[1px]">
                                <SpotifyPanel
                                    onSubmit={(d) =>
                                        api("rpc/set-spotify", d)
                                    }
                                    loading={loading}
                                />
                            </div>

                            <div className="absolute inset-0 z-10 flex items-center justify-center">
                                <div className="mx-auto w-full max-w-xl rounded-2xl border border-white/10 bg-black/40 p-8 text-center backdrop-blur-xl">
                                    <div className="text-sm font-semibold tracking-wider text-white/60">
                                        Spotify Lyrics
                                    </div>
                                    <div className="mt-2 text-3xl font-semibold text-white">
                                        Coming soon
                                    </div>
                                    <div className="mt-2 text-sm text-white/55">
                                        We're building a real Spotify integration with lyrics display (auto-detect, art, progress, and sync).
                                    </div>
                                </div>
                            </div>
                        </div>
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
                    Spotify Lyrics
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
