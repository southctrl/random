"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { BrandedBackground } from "@/components/branded-background"
import { Button } from "@/components/ui/button"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { ArrowLeft, Loader2, MessageSquare, Settings } from "lucide-react"
import { useAutoSave } from "@/hooks/use-auto-save"
import { SaveChanges } from "@/components/layout/SaveChanges"
import { UnsavedChangesDialog } from "@/components/layout/UnsavedChangesDialog"
import { useCloudSettings } from "@/hooks/use-cloud-settings"
import { useNavigationProtection } from "@/hooks/use-navigation-protection"

const API_RPC = "/api/rpc"

function rpcErrorMessage(data: unknown): string {
    if (!data || typeof data !== "object") return "Request failed"
    const d = data as Record<string, unknown>
    const detail = d.detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
        const msg = (detail[0] as { msg?: string }).msg
        if (typeof msg === "string") return msg
    }
    if (typeof d.error === "string") return d.error
    return "Request failed"
}

interface SettingsData {
    discordToken: string
}

export default function DashboardSettingsPage() {
    const router = useRouter()
    const { data: sessionData, isPending } = authClient.useSession()
    const [saving, setSaving] = useState(false)
    const [mounted, setMounted] = useState(false)
    const { updateSettings, isSyncing } = useCloudSettings()

    const getInitialData = useCallback((): SettingsData => {
        if (typeof window === "undefined") return { discordToken: "" }
        const stored = localStorage.getItem("discord_token")
        return { discordToken: stored || "" }
    }, [])

    const {
        data: settings,
        setData: setSettings,
        hasUnsavedChanges,
        isSaving: isAutoSaving,
        save,
        showDialog,
        setShowDialog,
        confirmNavigation,
        cancelNavigation,
        lastSynced,
    } = useAutoSave<SettingsData>({
        initialData: getInitialData(),
        onSave: async (data) => {
            if (data.discordToken.trim()) {
                localStorage.setItem("discord_token", data.discordToken.trim())
            }
        },
        onCloudSync: async (data) => {
            await updateSettings({
                app_settings: { discordTokenStored: !!data.discordToken } as Record<string, unknown>,
            })
        },
        requireExplicitSave: true,
    })

    const { showDialog: showNavigationDialog, onConfirm: handleNavigationConfirm, onCancel: handleNavigationCancel } = useNavigationProtection({
        hasUnsavedChanges,
        onConfirmNavigation: () => {
            console.log(" [SETTINGS] Navigation confirmed")
            confirmNavigation()
        },
        onCancelNavigation: () => {
            console.log(" [SETTINGS] Navigation cancelled")
            cancelNavigation()
        },
    })

    useEffect(() => {
        setMounted(true)
    }, [])

    useEffect(() => {
        if (isPending) return
        if (!sessionData?.session) {
            router.replace("/login")
        }
    }, [isPending, sessionData, router])

    const saveTokenOnly = async () => {
        const trimmed = settings.discordToken.trim()
        if (!trimmed) {
            toast.error("Enter a token or clear the field to remove it")
            return
        }
        await save()
    }

    const removeToken = async () => {
        localStorage.removeItem("discord_token")
        setSettings({ discordToken: "" })
        toast.success("Token removed from this browser")
    }

    const saveAndConnect = async (e: React.FormEvent) => {
        e.preventDefault()
        const trimmed = settings.discordToken.trim()
        if (!trimmed) {
            toast.error("Paste your Discord user token")
            return
        }
        
        await save()
        
        setSaving(true)
        try {
            const res = await fetch(`${API_RPC}/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: trimmed }),
            })
            const data = await res.json().catch(() => ({}))
            if (!res.ok) {
                throw new Error(rpcErrorMessage(data))
            }
            toast.success(
                typeof data.message === "string"
                    ? data.message
                    : "Connected to RPC backend"
            )
            router.push("/dashboard")
        } catch (err) {
            toast.error(
                err instanceof Error ? err.message : "Could not reach RPC backend"
            )
        } finally {
            setSaving(false)
        }
    }

    if (!mounted || isPending) {
        return (
            <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
                <BrandedBackground />
                <Loader2 className="relative z-10 h-10 w-10 animate-spin text-white/80" />
            </div>
        )
    }

    if (!sessionData?.session) {
        return null
    }

    return (
        <div className="relative min-h-screen overflow-hidden">
            <BrandedBackground />
            <header className="relative z-20 flex h-16 items-center border-b border-white/10 bg-black/30 px-4 backdrop-blur-md sm:px-8">
                <div className="flex min-w-0 flex-1 items-center gap-3 sm:gap-5">
                    <Link
                        href="/dashboard"
                        className="flex shrink-0 items-center gap-2 rounded-lg py-1.5 text-sm font-light text-white/75 transition-colors hover:bg-white/5 hover:text-white"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        <span className="hidden sm:inline">Dashboard</span>
                    </Link>
                    <span
                        className="hidden h-6 w-px shrink-0 bg-white/15 sm:block"
                        aria-hidden
                    />
                    <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[#47a6ff] to-[#2563eb]">
                            <MessageSquare className="h-5 w-5 text-white" />
                        </div>
                        <div className="min-w-0">
                            <p className="truncate font-sans text-xs text-white/50">
                                Expel
                            </p>
                            <div className="flex items-center gap-2">
                                <Settings
                                    className="h-4 w-4 shrink-0 text-[#47a6ff]"
                                    aria-hidden
                                />
                                <h1 className="truncate font-sans text-base font-light text-white italic sm:text-lg">
                                    Settings
                                </h1>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <div className="relative z-10 mx-auto max-w-lg px-4 py-8 sm:py-10">
                <Card className="border-white/20 bg-black/35 text-white shadow-xl backdrop-blur-md">
                    <CardHeader>
                        <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/10">
                                <Settings className="h-5 w-5 text-[#47a6ff]" />
                            </div>
                            <div>
                                <p className="font-sans text-xs font-light tracking-[0.2em] text-white/60 uppercase">
                                    Account
                                </p>
                                <CardTitle className="font-sans text-2xl font-light text-white italic">
                                    Discord token
                                </CardTitle>
                            </div>
                        </div>
                        <CardDescription className="text-white/65">
                            Stored only in your browser. Used to connect the RPC
                            backend to your Discord session. Updating here
                            replaces the token from onboarding.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={saveAndConnect} className="space-y-6">
                            <div className="space-y-2">
                                <Label
                                    htmlFor="discord-token"
                                    className="text-white/90"
                                >
                                    User token
                                </Label>
                                <Input
                                    id="discord-token"
                                    type="password"
                                    autoComplete="off"
                                    value={settings.discordToken}
                                    onChange={(e) =>
                                        setSettings((prev) => ({ ...prev, discordToken: e.target.value }))
                                    }
                                    placeholder="Paste token"
                                    className="border-white/30 bg-white/10 font-mono text-sm text-white placeholder:text-white/45 focus-visible:ring-[#47a6ff]/50"
                                />
                                <p className="text-xs text-white/50">
                                    Ensure the Python backend is running if you
                                    use “Save &amp; connect”.
                                </p>
                            </div>

                            <div className="flex flex-col gap-3 sm:flex-row">
                                <Button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 rounded-full border border-white/30 bg-[#47a6ff]/90 text-white hover:bg-[#47a6ff]"
                                >
                                    {saving ? (
                                        <>
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            Connecting…
                                        </>
                                    ) : (
                                        "Save & connect"
                                    )}
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    disabled={saving}
                                    onClick={saveTokenOnly}
                                    className="rounded-full border-white/30 bg-transparent text-white hover:bg-white/10"
                                >
                                    Save locally only
                                </Button>
                            </div>

                            <Button
                                type="button"
                                variant="ghost"
                                onClick={removeToken}
                                className="w-full text-red-300/90 hover:bg-red-500/10 hover:text-red-200"
                            >
                                Remove token from this browser
                            </Button>

                            <SaveChanges
                                show={hasUnsavedChanges}
                                saving={isAutoSaving}
                                onSave={save}
                                isSyncing={isSyncing}
                                lastSynced={lastSynced}
                            />
                        </form>
                    </CardContent>
                </Card>
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
        </div>
    )
}
