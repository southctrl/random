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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { useCloudSettings } from "@/hooks/use-cloud-settings"
import { useCloudSyncManager } from "@/hooks/use-cloud-sync-manager"
import { useNavigationProtection } from "@/hooks/use-navigation-protection"
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
    Plus,
    Edit,
    X,
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

interface RotationStatus {
    id: number
    emoji: string
    text: string
    interval: number
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
        
        if (res.status === 401) {
            localStorage.removeItem("discord_token")
            window.location.href = "/invalid-token"
            return { unreachable: false, data: null }
        }
        
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

export default function CustomPage() {
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
        const savedExpandedCategories = localStorage.getItem("expanded_categories")
        if (savedExpandedCategories) {
            try {
                setExpandedCategories(new Set(JSON.parse(savedExpandedCategories)))
            } catch (error) {
                console.error("Failed to load saved expanded categories:", error)
            }
        }
    }, [])

    useEffect(() => {
        localStorage.setItem("expanded_categories", JSON.stringify(Array.from(expandedCategories)))
    }, [expandedCategories])

    useEffect(() => {
        if (sessionPending) return
        const init = async () => {
            if (!sessionAuth?.session) {
                router.push("/login")
                return
            }
            
            let discordToken = localStorage.getItem("discord_token")
            
            if (!discordToken) {
                try {
                    const response = await fetch("/api/user/save-discord-token", {
                        headers: {
                            "Content-Type": "application/json",
                        },
                    })
                    
                    if (response.ok) {
                        const data = await response.json()
                        if (data.token && typeof data.token === "string") {
                            discordToken = data.token
                            localStorage.setItem("discord_token", data.token)
                            console.log("Token retrieved from user account")
                        }
                    }
                } catch (error) {
                    console.error("Failed to retrieve token from account:", error)
                }
            }
            
            if (!discordToken) {
                router.push("/onboarding")
                return
            }
            
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
            
            if (res.status === 401) {
                localStorage.removeItem("discord_token")
                window.location.href = "/invalid-token"
                return null
            }
            
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
                
                if (res.status === 401) {
                    localStorage.removeItem("discord_token")
                    window.location.href = "/invalid-token"
                    setIsConnecting(false)
                    return
                }
                
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
                    title="Custom Status" 
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
                        <CustomPanel
                            onSubmit={(d) =>
                                api(
                                    "rpc/set-custom-status",
                                    {
                                        text: d.text,
                                        emoji: d.emoji
                                    }
                                )
                            }
                            loading={loading}
                        />
                        <RotationPanel loading={loading} />
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
                    Custom Status
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

interface CustomStatusForm {
    emoji: string
    text: string
}

function CustomPanel({
    onSubmit,
    loading,
}: {
    onSubmit: (d: { emoji?: string; text?: string }) => void
    loading: boolean
}) {
    const { updateSettings, isSyncing } = useCloudSettings()
    const { saveToCloud, syncStatus, isCloudFirst, isLoading } = useCloudSyncManager()
    const [emojiError, setEmojiError] = useState("")
    const hydratedRef = useRef(false)

    const getInitialForm = (): CustomStatusForm => {
        if (typeof window === "undefined") return { emoji: "", text: "" }
        
        if (isCloudFirst) {
            console.log("[CUSTOM STATUS] Cloud-first mode - checking cloud data...")
            return { emoji: "", text: "" }
        }
        
        const saved = localStorage.getItem("custom_status")
        if (saved) {
            try {
                return JSON.parse(saved)
            } catch {
                return { emoji: "", text: "" }
            }
        }
        return { emoji: "", text: "" }
    }

    const {
        data: form,
        setData: setForm,
        hasUnsavedChanges,
        isSaving,
        save,
        showDialog,
        setShowDialog,
        confirmNavigation,
        cancelNavigation,
        lastSynced,
    } = useAutoSave<CustomStatusForm>({
        initialData: getInitialForm(),
        onSave: async (data) => {
            if (data.emoji || data.text) {
                localStorage.setItem("custom_status", JSON.stringify(data))
            } else {
                localStorage.removeItem("custom_status")
            }
        },
        onCloudSync: async (data) => {
            await updateSettings({
                custom_rpc_settings: { 
                    customStatus: data
                } as Record<string, unknown>,
            })
        },
        requireExplicitSave: true,
    })

    const loadCloudData = useCallback(async () => {
        try {
            const response = await fetch("/api/user/settings")
            if (response.ok) {
                const data = await response.json()
                const cloudSettings = data.settings
                const cloudCustomStatus = cloudSettings?.custom_rpc_settings?.customStatus as CustomStatusForm
                
                if (cloudCustomStatus) {
                    console.log("[CUSTOM STATUS] Loaded cloud data:", cloudCustomStatus)
                    setForm(cloudCustomStatus)
                    
                    localStorage.removeItem("custom_status")
                    console.log("[CUSTOM STATUS] Cleared local storage for cloud-first mode")
                    
                    toast.success("Custom status loaded from cloud")
                } else {
                    console.log("[CUSTOM STATUS] No cloud data found, using defaults")
                }
            }
        } catch (error) {
            console.error("[CUSTOM STATUS] Error loading cloud data:", error)
            toast.error("Failed to load settings from cloud")
        }
    }, [])

    useEffect(() => {
        if (isCloudFirst && syncStatus === "synced" && !hydratedRef.current) {
            console.log("[CUSTOM STATUS] Loading cloud data in cloud-first mode...")
            loadCloudData()
            hydratedRef.current = true
        }
    }, [isCloudFirst, syncStatus, loadCloudData])

    const isValidEmoji = (emoji: string): boolean => {
        if (!emoji) return true
        
        const unicodeEmojiRegex = /^[\u{1F600}-\u{1F64F}]$|^[\u{1F300}-\u{1F5FF}]$|^[\u{1F680}-\u{1F6FF}]$|^[\u{1F700}-\u{1F77F}]$|^[\u{1F780}-\u{1F7FF}]$|^[\u{1F800}-\u{1F8FF}]$|^[\u{2600}-\u{26FF}]$|^[\u{2700}-\u{27BF}]$/u
        
        const discordEmojiRegex = /^<a?:[\w_]{2,32}:\d{17,22}>$|^<:[\w_]{2,32}:\d{17,22}>$/
        
        return unicodeEmojiRegex.test(emoji) || discordEmojiRegex.test(emoji)
    }

    const handleEmojiChange = (value: string) => {
        setForm((f) => ({ ...f, emoji: value }))
        
        if (value && !isValidEmoji(value)) {
            setEmojiError("Invalid emoji format. Use a single emoji or Discord custom emoji format.")
        } else {
            setEmojiError("")
        }
    }

    const handleSubmit = async () => {
        if (!form.emoji && !form.text) return
        
        if (form.emoji && !isValidEmoji(form.emoji)) {
            setEmojiError("Invalid emoji format. Use a single emoji or Discord custom emoji format.")
            return
        }
        
        if (hasUnsavedChanges) {
            await save()
        }
        
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
                        onChange={(e) => handleEmojiChange(e.target.value)}
                        placeholder="any of these are accepted: 👋, <a:emoji_name:123456789>, <:emoji_name:123456789>"
                        maxLength={40}
                        disabled={loading}
                        className={`border-white/10 bg-white/5 text-white ${emojiError ? "border-red-500" : ""}`}
                    />
                    {emojiError && (
                        <p className="mt-1 text-xs text-red-400">{emojiError}</p>
                    )}
                    <p className="mt-1 text-xs text-white/45">
                        Single emoji or Discord custom emoji (max 40 chars)
                    </p>
                </div>
                
                <div>
                    <Label htmlFor="text" className="text-white/80">Status Text</Label>
                    <Input
                        id="text"
                        value={form.text}
                        onChange={(e) => setForm((f) => ({ ...f, text: e.target.value.slice(0, 128) }))}
                        placeholder="Working on something amazing..."
                        maxLength={128}
                        disabled={loading}
                        className="border-white/10 bg-white/5 text-white"
                    />
                    <p className="mt-1 text-xs text-white/45">
                        {form.text.length}/128 characters
                    </p>
                </div>

                <SaveChanges
                    show={hasUnsavedChanges}
                    saving={isSaving}
                    onSave={save}
                    isSyncing={isSyncing}
                    lastSynced={lastSynced}
                />

                <Button
                    onClick={handleSubmit}
                    disabled={loading || (!form.emoji && !form.text) || !!emojiError || hasUnsavedChanges}
                    className="w-full gap-2 rounded-lg border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    {loading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Check className="h-4 w-4" />
                    )}
                    {hasUnsavedChanges ? "Save changes first" : "Set Custom Status"}
                </Button>
            </div>

            <UnsavedChangesDialog
                open={showDialog}
                onOpenChange={setShowDialog}
                onConfirm={confirmNavigation}
                onCancel={cancelNavigation}
            />
        </div>
    )
}

function RotationPanel({ loading }: { loading: boolean }) {
    const { updateSettings } = useCloudSettings()
    const { saveToCloud, syncStatus, isCloudFirst, isLoading } = useCloudSyncManager()
    const [rotationStatuses, setRotationStatuses] = useState<RotationStatus[]>([])
    const [form, setForm] = useState({ emoji: "", text: "", interval: 5 })
    const [emojiError, setEmojiError] = useState("")
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editForm, setEditForm] = useState({ emoji: "", text: "", interval: 5 })
    const [isRotating, setIsRotating] = useState(false)
    const [currentRotationIndex, setCurrentRotationIndex] = useState(0)
    const [rotationInterval, setRotationInterval] = useState<NodeJS.Timeout | null>(null)
    const hydratedRef = useRef(false)
    const justSavedRef = useRef(false)

    const getInitialData = (): RotationStatus[] => {
        if (typeof window === "undefined") return []
        
        if (isCloudFirst) {
            console.log("[ROTATION] Cloud-first mode - will load from cloud...")
            return []
        }
        
        const saved = localStorage.getItem("rotation_statuses")
        if (saved) {
            try {
                return JSON.parse(saved)
            } catch (error) {
                console.error("Failed to load saved rotation statuses:", error)
                return []
            }
        }
        return []
    }

    const [savedRotationStatuses, setSavedRotationStatuses] = useState<RotationStatus[]>(getInitialData())
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [showDialog, setShowDialog] = useState(false)
    const [lastSynced, setLastSynced] = useState<Date | null>(null)

    useEffect(() => {
        setRotationStatuses(savedRotationStatuses)
    }, [savedRotationStatuses])

    useEffect(() => {
        console.log("🔒 [ROTATION] hasUnsavedChanges changed to:", hasUnsavedChanges)
    }, [hasUnsavedChanges])

    const updateRotationStatuses = useCallback((newStatuses: RotationStatus[]) => {
        const currentData = JSON.stringify(savedRotationStatuses)
        const newData = JSON.stringify(newStatuses)
        const hasChanges = currentData !== newData
        console.log("🔒 [ROTATION] updateRotationStatuses called:", { hasChanges, currentLength: savedRotationStatuses.length, newLength: newStatuses.length })
        setHasUnsavedChanges(hasChanges)
        setSavedRotationStatuses(newStatuses)
    }, [savedRotationStatuses])

    const save = useCallback(async () => {
        if (!hasUnsavedChanges) return

        console.log("[ROTATION] Starting save process...")
        console.log("[ROTATION] Data to save:", savedRotationStatuses)

        setIsSaving(true)
        try {
            if (savedRotationStatuses.length > 0) {
                localStorage.setItem("rotation_statuses", JSON.stringify(savedRotationStatuses))
                console.log("[ROTATION] Saved to localStorage")
            } else {
                localStorage.removeItem("rotation_statuses")
                console.log("[ROTATION] Cleared localStorage")
            }

            console.log("[ROTATION] Calling updateSettings...")
            await updateSettings({
                custom_rpc_settings: { 
                    rotationStatuses: savedRotationStatuses
                } as Record<string, unknown>,
            })
            console.log("[ROTATION] updateSettings completed successfully")

            setHasUnsavedChanges(false)
            setLastSynced(new Date())
            justSavedRef.current = true
            setTimeout(() => {
                justSavedRef.current = false
            }, 2000)

            toast.success("Changes saved and synced to cloud")
            console.log("[ROTATION] Save process completed successfully")
        } catch (error) {
            console.error("[ROTATION] Save failed:", error)
            toast.error("Failed to save changes")
        } finally {
            setIsSaving(false)
        }
    }, [hasUnsavedChanges, savedRotationStatuses, updateSettings])

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
            console.log("🔒 [ROTATION] Navigation confirmed")
            confirmNavigation()
        },
        onCancelNavigation: () => {
            console.log("🔒 [ROTATION] Navigation cancelled")
            cancelNavigation()
        },
    })

    useEffect(() => {
        localStorage.setItem("rotation_active", JSON.stringify(isRotating))
        if (isRotating) {
            localStorage.setItem("rotation_index", JSON.stringify(currentRotationIndex))
        }
    }, [isRotating, currentRotationIndex])

    useEffect(() => {
        const savedRotationActive = localStorage.getItem("rotation_active")
        const savedRotationIndex = localStorage.getItem("rotation_index")
        if (savedRotationActive && rotationStatuses.length > 0) {
            try {
                const wasRotating = JSON.parse(savedRotationActive)
                const index = savedRotationIndex ? JSON.parse(savedRotationIndex) : 0
                if (wasRotating) {
                    setCurrentRotationIndex(index)
                }
            } catch (error) {
                console.error("Failed to load saved rotation state:", error)
            }
        }
    }, [rotationStatuses.length])

    const loadCloudData = useCallback(async () => {
        try {
            const response = await fetch("/api/user/settings")
            if (response.ok) {
                const data = await response.json()
                const cloudSettings = data.settings
                const cloudRotationStatuses = cloudSettings?.custom_rpc_settings?.rotationStatuses as RotationStatus[]
                
                if (cloudRotationStatuses && cloudRotationStatuses.length > 0) {
                    console.log("[ROTATION] Loaded cloud rotation statuses:", cloudRotationStatuses)
                    
                    if (JSON.stringify(cloudRotationStatuses) !== JSON.stringify(savedRotationStatuses)) {
                        setSavedRotationStatuses(cloudRotationStatuses)
                        setHasUnsavedChanges(false)
                        localStorage.removeItem("rotation_statuses")
                        console.log("[ROTATION] Cleared local storage for cloud-first mode")
                        toast.success("Rotation statuses loaded from cloud")
                    }
                } else {
                    console.log("[ROTATION] No cloud rotation data found, using defaults")
                }
            }
        } catch (error) {
            console.error("[ROTATION] Error loading cloud data:", error)
            toast.error("Failed to load rotation settings from cloud")
        }
    }, [savedRotationStatuses])

    useEffect(() => {
        if (isCloudFirst && syncStatus === "synced" && !hydratedRef.current && !justSavedRef.current) {
            console.log("[ROTATION] Loading cloud data in cloud-first mode...")
            loadCloudData()
            hydratedRef.current = true
        }
    }, [isCloudFirst, syncStatus, loadCloudData, justSavedRef.current])

    const isValidEmoji = (emoji: string): boolean => {
        if (!emoji) return true
        
        const unicodeEmojiRegex = /^[\u{1F600}-\u{1F64F}]$|^[\u{1F300}-\u{1F5FF}]$|^[\u{1F680}-\u{1F6FF}]$|^[\u{1F700}-\u{1F77F}]$|^[\u{1F780}-\u{1F7FF}]$|^[\u{1F800}-\u{1F8FF}]$|^[\u{2600}-\u{26FF}]$|^[\u{2700}-\u{27BF}]$/u
        
        const discordEmojiRegex = /^<a?:[\w_]{2,32}:\d{17,22}>$|^<:[\w_]{2,32}:\d{17,22}>$/
        
        return unicodeEmojiRegex.test(emoji) || discordEmojiRegex.test(emoji)
    }

    const handleEmojiChange = (value: string) => {
        setForm((f) => ({ ...f, emoji: value }))
        
        if (value && !isValidEmoji(value)) {
            setEmojiError("Invalid emoji format. Use a single emoji or Discord custom emoji format.")
        } else {
            setEmojiError("")
        }
    }

    const handleAddToRotation = () => {
        if (!form.emoji && !form.text) return
        
        if (form.emoji && !isValidEmoji(form.emoji)) {
            setEmojiError("Invalid emoji format. Use a single emoji or Discord custom emoji format.")
            return
        }
        
        const newStatus: RotationStatus = {
            id: Date.now(),
            emoji: form.emoji,
            text: form.text,
            interval: form.interval
        }
        
        updateRotationStatuses([...rotationStatuses, newStatus])
        setForm({ emoji: "", text: "", interval: 5 })
        setEmojiError("")
    }

    const handleEdit = (status: RotationStatus) => {
        setEditingId(status.id)
        setEditForm({
            emoji: status.emoji,
            text: status.text,
            interval: status.interval
        })
    }

    const handleSaveEdit = () => {
        if (editingId === null) return
        
        const updatedStatuses = rotationStatuses.map(status =>
            status.id === editingId
                ? { ...status, ...editForm }
                : status
        )
        
        updateRotationStatuses(updatedStatuses)
        setEditingId(null)
        setEditForm({ emoji: "", text: "", interval: 5 })
    }

    const handleCancelEdit = () => {
        setEditingId(null)
        setEditForm({ emoji: "", text: "", interval: 5 })
    }

    const handleDelete = (id: number) => {
        const updatedStatuses = rotationStatuses.filter(status => status.id !== id)
        updateRotationStatuses(updatedStatuses)
    }

    const setCustomStatus = async (emoji: string, text: string) => {
        try {
            const token = localStorage.getItem("discord_token")
            if (!token) return

            const res = await fetch(`${API_BASE}/rpc/set-custom-status`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ text, emoji }),
            })
            
            if (res.ok) {
                console.log("Status updated successfully")
            } else if (res.status === 401) {
                console.error("Token invalid or expired")
                stopRotation()
                window.location.href = "/invalid-token"
            } else {
                console.error("Failed to update status")
            }
        } catch (error) {
            console.error("Error setting custom status:", error)
        }
    }

    const startRotation = () => {
        if (rotationStatuses.length === 0) return
        
        setIsRotating(true)
        setCurrentRotationIndex(0)
        
        const firstStatus = rotationStatuses[0]
        setCustomStatus(firstStatus.emoji, firstStatus.text)
        
        const scheduleNextRotation = (currentIndex: number) => {
            const currentStatus = rotationStatuses[currentIndex]
            const timeout = setTimeout(() => {
                const nextIndex = (currentIndex + 1) % rotationStatuses.length
                const nextStatus = rotationStatuses[nextIndex]
                setCustomStatus(nextStatus.emoji, nextStatus.text)
                setCurrentRotationIndex(nextIndex)
                
                scheduleNextRotation(nextIndex)
            }, currentStatus.interval * 1000)
            
            setRotationInterval(timeout)
        }
        
        scheduleNextRotation(0)
    }

    const stopRotation = () => {
        if (rotationInterval) {
            clearTimeout(rotationInterval)
            setRotationInterval(null)
        }
        setIsRotating(false)
        setCurrentRotationIndex(0)
    }

    useEffect(() => {
        return () => {
            if (rotationInterval) {
                clearTimeout(rotationInterval)
            }
        }
    }, [rotationInterval])

    return (
        <>
            <div className="my-8 border-t border-white/10"></div>
            
            <div className="rounded-xl border border-white/10 bg-black/35 p-6 backdrop-blur-sm">
                <h3 className="mb-6 flex items-center gap-2 text-base font-medium text-white">
                    <RefreshCw className="h-4 w-4 text-[#47a6ff]" />
                    Rotate Custom Statuses
                </h3>
                
                <div className="space-y-4">
                    <div>
                        <Label htmlFor="rotation-emoji" className="text-white/80">Emoji</Label>
                        <Input
                            id="rotation-emoji"
                            value={form.emoji}
                            onChange={(e) => handleEmojiChange(e.target.value)}
                            placeholder="any of these are accepted: 👋, <a:emoji_name:123456789>, <:emoji_name:123456789>"
                            maxLength={40}
                            disabled={loading}
                            className={`border-white/10 bg-white/5 text-white ${emojiError ? "border-red-500" : ""}`}
                        />
                        {emojiError && (
                            <p className="mt-1 text-xs text-red-400">{emojiError}</p>
                        )}
                        <p className="mt-1 text-xs text-white/45">
                            Single emoji or Discord custom emoji (max 40 chars)
                        </p>
                    </div>
                    
                    <div>
                        <Label htmlFor="rotation-text" className="text-white/80">Status Text</Label>
                        <Input
                            id="rotation-text"
                            value={form.text}
                            onChange={(e) => setForm((f) => ({ ...f, text: e.target.value.slice(0, 128) }))}
                            placeholder="Working on something amazing..."
                            maxLength={128}
                            disabled={loading}
                            className="border-white/10 bg-white/5 text-white"
                        />
                        <p className="mt-1 text-xs text-white/45">
                            {form.text.length}/128 characters
                        </p>
                    </div>

                    <div>
                        <Label htmlFor="rotation-interval" className="text-white/80">Interval (seconds)</Label>
                        <Input
                            id="rotation-interval"
                            type="number"
                            min="1"
                            max="86400"
                            value={form.interval}
                            onChange={(e) => setForm((f) => ({ ...f, interval: Math.max(1, Math.min(86400, parseInt(e.target.value) || 1)) }))}
                            placeholder="5"
                            disabled={loading}
                            className="border-white/10 bg-white/5 text-white"
                        />
                        <p className="mt-1 text-xs text-white/45">
                            Time between rotations (1-86400 seconds)
                        </p>
                    </div>

                    <Button
                        onClick={handleAddToRotation}
                        disabled={loading || (!form.emoji && !form.text) || !!emojiError}
                        className="w-full gap-2 rounded-lg border-sky-500/25 bg-sky-500/10 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                    >
                        {loading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Plus className="h-4 w-4" />
                        )}
                        Add custom status to rotation
                    </Button>

                    {rotationStatuses.length > 0 && (
                        <div className="flex gap-2">
                            <Button
                                onClick={isRotating ? stopRotation : startRotation}
                                disabled={loading}
                                className={`flex-1 gap-2 rounded-lg border ${
                                    isRotating 
                                        ? "border-red-500/25 bg-red-500/10 text-red-400 hover:border-red-400/40 hover:bg-red-500/20"
                                        : "border-green-500/25 bg-green-500/10 text-green-400 hover:border-green-400/40 hover:bg-green-500/20"
                                }`}
                            >
                                {isRotating ? (
                                    <>
                                        <X className="h-4 w-4" />
                                        Stop Rotation
                                    </>
                                ) : (
                                    <>
                                        <RefreshCw className="h-4 w-4" />
                                        Start Rotation
                                    </>
                                )}
                            </Button>
                        </div>
                    )}
                </div>
            </div>

            {rotationStatuses.length > 0 && (
                <div className="mt-6 rounded-xl border border-white/10 bg-black/35 p-6 backdrop-blur-sm">
                    <h4 className="mb-4 text-sm font-medium text-white/80">
                        Rotation Statuses ({rotationStatuses.length})
                    </h4>
                    <div className="space-y-2">
                        {rotationStatuses.map((status, index) => (
                            <div
                                key={status.id}
                                className={`flex items-center gap-2 rounded-lg border p-3 ${
                                    isRotating && index === currentRotationIndex
                                        ? "border-sky-500/50 bg-sky-500/10"
                                        : "border-white/10 bg-white/5"
                                }`}
                            >
                                <span className="flex-1 text-sm text-white/60">
                                    ID: {status.id}
                                    {isRotating && index === currentRotationIndex && (
                                        <span className="ml-2 text-xs text-sky-400">● Active</span>
                                    )}
                                </span>
                                
                                {editingId === status.id ? (
                                    <>
                                        <Input
                                            value={editForm.emoji}
                                            onChange={(e) => setEditForm((f) => ({ ...f, emoji: e.target.value }))}
                                            placeholder="Emoji"
                                            className="w-20 border-white/10 bg-white/5 text-white"
                                        />
                                        <Input
                                            value={editForm.text}
                                            onChange={(e) => setEditForm((f) => ({ ...f, text: e.target.value }))}
                                            placeholder="Text"
                                            className="w-32 border-white/10 bg-white/5 text-white"
                                        />
                                        <Input
                                            type="number"
                                            value={editForm.interval}
                                            onChange={(e) => setEditForm((f) => ({ ...f, interval: Math.max(1, parseInt(e.target.value) || 1) }))}
                                            placeholder="Interval"
                                            className="w-20 border-white/10 bg-white/5 text-white"
                                        />
                                        <Button
                                            size="sm"
                                            onClick={handleSaveEdit}
                                            className="h-8 w-8 border-green-500/25 bg-green-500/10 text-green-400 hover:border-green-400/40 hover:bg-green-500/20"
                                        >
                                            <Check className="h-3 w-3" />
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={handleCancelEdit}
                                            className="h-8 w-8 border-red-500/25 bg-red-500/10 text-red-400 hover:border-red-400/40 hover:bg-red-500/20"
                                        >
                                            <X className="h-3 w-3" />
                                        </Button>
                                    </>
                                ) : (
                                    <>
                                        <span className="flex-1 text-sm text-white">
                                            {status.emoji && <span className="mr-2">{status.emoji}</span>}
                                            {status.text}
                                        </span>
                                        <span className="text-xs text-white/45">
                                            {status.interval}s
                                        </span>
                                        <Button
                                            size="sm"
                                            onClick={() => handleEdit(status)}
                                            className="h-8 w-8 border-sky-500/25 bg-sky-500/10 text-sky-400 hover:border-sky-400/40 hover:bg-sky-500/20"
                                        >
                                            <Edit className="h-3 w-3" />
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={() => handleDelete(status.id)}
                                            className="h-8 w-8 border-red-500/25 bg-red-500/10 text-red-400 hover:border-red-400/40 hover:bg-red-500/20"
                                        >
                                            <Trash2 className="h-3 w-3" />
                                        </Button>
                                    </>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <SaveChanges
                show={hasUnsavedChanges}
                saving={isSaving}
                onSave={save}
                lastSynced={lastSynced}
            />

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
