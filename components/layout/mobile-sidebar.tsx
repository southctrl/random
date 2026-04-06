"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from "@/components/ui/sheet"
import {
    Menu,
    X,
    Circle,
    Gamepad2,
    Music,
    Sparkles,
    User,
    LogOut,
    Settings,
    Wifi,
    WifiOff,
    ChevronDown,
    ChevronRight,
    RefreshCw,
    Loader2,
    Cloud,
    CloudOff,
    Home,
    ArrowLeft,
    Trash2,
} from "lucide-react"

type Status = "online" | "idle" | "dnd" | "invisible"

interface NavItem {
    id: string
    label: string
    icon: string
}

interface NavCategory {
    category: string
    href: string
    items: NavItem[]
}

interface MobileSidebarProps {
    navItems: NavCategory[]
    connected: boolean
    status: Status
    avatarUrl: string | null
    userName: string
    isSyncing?: boolean
    onConnect?: () => void
    isConnecting?: boolean
    onSignOut: () => void
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
        case "settings":
            return <Settings className={className} />
        case "home":
            return <Home className={className} />
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

export function MobileSidebar({
    navItems,
    connected,
    status,
    avatarUrl,
    userName,
    isSyncing = false,
    onConnect,
    isConnecting = false,
    onSignOut,
}: MobileSidebarProps) {
    const [open, setOpen] = useState(false)
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
        new Set(navItems.map(cat => cat.category))
    )
    const pathname = usePathname()

    useEffect(() => {
        setOpen(false)
    }, [pathname])

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

    return (
        <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="md:hidden fixed top-4 left-4 z-50 h-10 w-10 rounded-full bg-black/50 backdrop-blur-sm border border-white/10 text-white hover:bg-white/10"
                    aria-label="Open menu"
                >
                    <Menu className="h-5 w-5" />
                </Button>
            </SheetTrigger>
            <SheetContent 
                side="left" 
                className="w-[280px] bg-black/95 backdrop-blur-xl border-white/10 p-0"
            >
                <SheetHeader className="sr-only">
                    <SheetTitle>Navigation Menu</SheetTitle>
                </SheetHeader>
                
                {/* User Profile Header */}
                <div className="flex items-center gap-3 border-b border-white/10 p-4">
                    {avatarUrl ? (
                        <div className="relative h-10 w-10 shrink-0">
                            <img
                                src={avatarUrl}
                                alt=""
                                width={40}
                                height={40}
                                className="h-10 w-10 rounded-full object-cover ring-1 ring-white/20"
                                referrerPolicy="no-referrer"
                            />
                            <span className="absolute -bottom-0.5 -right-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-black ring-2 ring-black">
                                <StatusDot status={status} className="h-3 w-3" />
                            </span>
                        </div>
                    ) : (
                        <div className="relative h-10 w-10 shrink-0">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 ring-1 ring-white/15">
                                <User className="h-5 w-5 text-white/50" />
                            </div>
                            <span className="absolute -bottom-0.5 -right-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-black ring-2 ring-black">
                                <StatusDot status={status} className="h-3 w-3" />
                            </span>
                        </div>
                    )}
                    <div className="flex-1 min-w-0">
                        <h2 className="text-sm font-semibold text-white truncate">
                            {userName}
                        </h2>
                        <div className="flex items-center gap-1.5 text-xs text-white/50">
                            {isSyncing ? (
                                <>
                                    <Cloud className="h-3 w-3 animate-pulse text-sky-400" />
                                    Syncing...
                                </>
                            ) : (
                                <>
                                    <Cloud className="h-3 w-3 text-green-400" />
                                    Cloud synced
                                </>
                            )}
                        </div>
                    </div>
                </div>

                {/* Connection Status */}
                <div className="border-b border-white/10 p-4">
                    <div className="flex items-center gap-2 text-xs text-white/50 mb-2">
                        {connected ? (
                            <>
                                <Wifi className="h-3.5 w-3.5 text-green-500" />
                                <span className="text-green-400">Connected to Discord</span>
                            </>
                        ) : (
                            <>
                                <WifiOff className="h-3.5 w-3.5 text-red-500" />
                                <span className="text-red-400">Disconnected</span>
                            </>
                        )}
                    </div>
                    {!connected && onConnect && (
                        <Button
                            onClick={onConnect}
                            disabled={isConnecting}
                            size="sm"
                            className="w-full bg-sky-500/20 border border-sky-500/30 text-sky-300 hover:bg-sky-500/30"
                        >
                            {isConnecting ? (
                                <>
                                    <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                                    Connecting...
                                </>
                            ) : (
                                <>
                                    <RefreshCw className="h-3.5 w-3.5 mr-2" />
                                    Connect
                                </>
                            )}
                        </Button>
                    )}
                </div>

                {/* Navigation */}
                <nav className="flex-1 overflow-y-auto p-3 space-y-2">
                    {/* Home Link */}
                    <Link
                        href="/dashboard"
                        className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                            pathname === "/dashboard"
                                ? "bg-sky-500/10 border border-sky-500/30 text-sky-300"
                                : "text-white/60 hover:bg-white/5 hover:text-white"
                        }`}
                    >
                        <Home className="h-4 w-4" />
                        Dashboard
                    </Link>

                    {navItems.map((category) => (
                        <div key={category.category}>
                            <button
                                onClick={() => toggleCategory(category.category)}
                                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white/70 hover:bg-white/5 transition-colors"
                            >
                                {expandedCategories.has(category.category) ? (
                                    <ChevronDown className="h-4 w-4" />
                                ) : (
                                    <ChevronRight className="h-4 w-4" />
                                )}
                                {category.category}
                            </button>
                            
                            {expandedCategories.has(category.category) && (
                                <div className="ml-3 mt-1 space-y-1">
                                    {category.items.map((item) => {
                                        const itemPath = `${category.href}/${item.id}`
                                        const isActive = pathname === itemPath || pathname.startsWith(itemPath + "/")
                                        
                                        return (
                                            <Link
                                                key={item.id}
                                                href={itemPath}
                                                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                                                    isActive
                                                        ? "bg-sky-500/10 border border-sky-500/30 text-sky-300"
                                                        : "text-white/50 hover:bg-white/5 hover:text-white"
                                                }`}
                                            >
                                                <Icon name={item.icon} />
                                                {item.label}
                                            </Link>
                                        )
                                    })}
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Settings Link */}
                    <Link
                        href="/dashboard/settings"
                        className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                            pathname === "/dashboard/settings"
                                ? "bg-sky-500/10 border border-sky-500/30 text-sky-300"
                                : "text-white/60 hover:bg-white/5 hover:text-white"
                        }`}
                    >
                        <Settings className="h-4 w-4" />
                        Settings
                    </Link>
                </nav>

                {/* Sign Out Button */}
                <div className="border-t border-white/10 p-4">
                    <Button
                        variant="ghost"
                        onClick={onSignOut}
                        className="w-full justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    >
                        <LogOut className="h-4 w-4" />
                        Sign Out
                    </Button>
                </div>
            </SheetContent>
        </Sheet>
    )
}

export function MobileHeader({
    title,
    onRefresh,
    refreshing = false,
    onClear,
    loading = false,
    connected = true,
}: {
    title: string
    onRefresh?: () => void
    refreshing?: boolean
    onClear?: () => void
    loading?: boolean
    connected?: boolean
}) {
    return (
        <div className="md:hidden fixed top-0 left-0 right-0 z-40 flex flex-col bg-black/80 backdrop-blur-xl border-b border-white/10">
            <div className="flex items-center justify-between h-14 px-4 pl-16">
                <div className="flex items-center gap-2 min-w-0">
                    <Link
                        href="/rpc/rich"
                        className="flex items-center gap-1 text-sm text-white/60 hover:text-white/90 transition-colors shrink-0"
                    >
                        <ArrowLeft className="h-3.5 w-3.5" />
                    </Link>
                    <h1 className="text-lg font-semibold text-white truncate">
                        {title}
                    </h1>
                </div>
                <div className="flex gap-1">
                    {onClear && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={onClear}
                            disabled={!connected || loading}
                            className="h-8 w-8 text-white/60 hover:text-white"
                        >
                            <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                    )}
                    {onRefresh && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={onRefresh}
                            disabled={refreshing}
                            className="h-8 w-8 text-white/60 hover:text-white"
                        >
                            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                        </Button>
                    )}
                </div>
            </div>
        </div>
    )
}
