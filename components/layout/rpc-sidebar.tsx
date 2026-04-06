"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { Button } from "@/components/ui/button"
import { MobileSidebar, MobileHeader } from "@/components/layout/mobile-sidebar"
import { toast } from "sonner"
import {
    Circle,
    Gamepad2,
    Music,
    Sparkles,
    LogOut,
    RefreshCw,
    Loader2,
    User,
    Wifi,
    WifiOff,
    Settings,
    ChevronDown,
    ChevronRight,
    Cloud,
    Home,
} from "lucide-react"

type Status = "online" | "idle" | "dnd" | "invisible"

const navItems = [
    {
        category: "RPC",
        href: "/rpc",
        items: [
            { id: "status", label: "Status", icon: "status" },
            { id: "custom", label: "Custom Status", icon: "custom" },
            { id: "rich", label: "Rich Presence", icon: "rich" },
            { id: "spotify", label: "Spotify Lyrics", icon: "spotify" },
        ]
    }
]

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

interface RpcSidebarProps {
    connected: boolean
    status: Status
    avatarUrl: string | null
    userName: string
    isSyncing?: boolean
    onConnect?: () => void
    isConnecting?: boolean
    onSignOut: () => void
}

export function RpcSidebar({
    connected,
    status,
    avatarUrl,
    userName,
    isSyncing = false,
    onConnect,
    isConnecting = false,
    onSignOut,
}: RpcSidebarProps) {
    const pathname = usePathname()
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
        new Set(["RPC"])
    )

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

    const getActiveTab = () => {
        const segments = pathname.split("/")
        const lastSegment = segments[segments.length - 1]
        return lastSegment
    }

    const activeTab = getActiveTab()

    return (
        <>
            {/* Mobile Sidebar */}
            <MobileSidebar
                navItems={navItems}
                connected={connected}
                status={status}
                avatarUrl={avatarUrl}
                userName={userName}
                isSyncing={isSyncing}
                onConnect={onConnect}
                isConnecting={isConnecting}
                onSignOut={onSignOut}
            />

            {/* Desktop Sidebar */}
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
                        <h1 className="text-sm font-semibold text-white truncate max-w-[140px]">{userName}</h1>
                        <div className="flex items-center gap-1 text-xs text-white/45">
                            {isSyncing ? (
                                <>
                                    <Cloud className="h-3 w-3 animate-pulse text-sky-400" />
                                    Syncing...
                                </>
                            ) : (
                                "Expel Selfbot"
                            )}
                        </div>
                    </div>
                </div>

                <nav className="flex-1 space-y-2 overflow-y-auto p-3">
                    {/* Dashboard Link */}
                    <Link
                        href="/dashboard"
                        className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-white/50 hover:bg-white/5 hover:text-white/90 transition-colors"
                    >
                        <Home className="h-4 w-4" />
                        Dashboard
                    </Link>

                    {navItems.map((category) => (
                        <div key={category.category}>
                            <button
                                onClick={() => toggleCategory(category.category)}
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
                    {!connected && onConnect && (
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
                            {isConnecting ? "Connecting..." : "Connect"}
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
        </>
    )
}

export { navItems }
export type { Status }
