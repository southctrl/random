"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { authClient } from "@/lib/auth-client"
import { BrandedBackground } from "@/components/branded-background"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import {
    ArrowLeft,
    ArrowRight,
    Check,
    Eye,
    EyeOff,
    HelpCircle,
    Info,
    Loader2,
    Shield,
    User,
    Cloud,
    CloudOff,
} from "lucide-react"
import { useDiscordToken } from "@/hooks/use-local-storage"
import { useCrossDeviceSync } from "@/hooks/use-cross-device-sync"

export default function OnboardingPage() {
    const router = useRouter()
    const { data: sessionData, isPending } = authClient.useSession()
    const [loading, setLoading] = useState(false)
    const [discordToken, setDiscordToken] = useDiscordToken()
    const [error, setError] = useState<string | null>(null)
    const [checkingCloudToken, setCheckingCloudToken] = useState(true)
    const [showTokenInput, setShowTokenInput] = useState(false)
    
    const { 
        cloudToken, 
        isLoading: cloudLoading, 
        hasCloudToken,
        syncTokenToCloud 
    } = useCrossDeviceSync()

    useEffect(() => {
        if (isPending || cloudLoading) return
        
        if (!sessionData?.session) {
            router.replace("/login")
            return
        }

        if (hasCloudToken && cloudToken) {
            localStorage.setItem("discord_token", cloudToken)
            localStorage.setItem("discord_token_validated", "true")
            toast.success("Token restored from cloud!", {
                description: "Your Discord token was synced from your account"
            })
            router.replace("/dashboard")
            return
        }

        setCheckingCloudToken(false)
        setShowTokenInput(true)
    }, [isPending, sessionData, router, cloudLoading, hasCloudToken, cloudToken])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!discordToken.trim()) {
            setError("Please enter your Discord token")
            return
        }

        setLoading(true)
        setError(null)

        try {
            const tokenToSave = discordToken.trim()
            
            const validateResponse = await fetch("/api/user/validate-token", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: tokenToSave }),
            })

            if (!validateResponse.ok) {
                const error = await validateResponse.json()
                throw new Error(error.message || "Invalid Discord token")
            }

            localStorage.setItem("discord_token", tokenToSave)
            localStorage.setItem("discord_token_validated", "true")
            
            await syncTokenToCloud(tokenToSave)
            
            toast.success("Token saved and synced!", {
                description: "Your token is now available on all your devices"
            })

            router.push("/dashboard")
        } catch (error) {
            console.error("Failed to save token:", error)
            setError(error instanceof Error ? error.message : "Failed to save token")
            toast.error("Failed to save token", {
                description: error instanceof Error ? error.message : "Please try again"
            })
        }
        setLoading(false)
    }

    const handleSkip = () => {
        router.push("/dashboard")
    }

    if (isPending || checkingCloudToken || cloudLoading) {
        return (
            <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
                <BrandedBackground />
                <div className="relative z-10 flex flex-col items-center gap-4">
                    <Loader2
                        className="h-10 w-10 animate-spin text-white/80"
                        aria-label="Loading"
                    />
                    {checkingCloudToken && (
                        <p className="text-sm text-white/60 flex items-center gap-2">
                            <Cloud className="h-4 w-4" />
                            Checking for synced token...
                        </p>
                    )}
                </div>
            </div>
        )
    }

    if (!sessionData?.session || !showTokenInput) {
        return null
    }

    return (
        <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
            <BrandedBackground />
            <Card className="relative z-10 w-full max-w-md border-white/20 bg-black/35 text-white shadow-xl backdrop-blur-md">
                <CardHeader className="space-y-1">
                    <p className="font-sans text-xs font-light tracking-[0.2em] text-white/60 uppercase">
                        Setup
                    </p>
                    <CardTitle className="font-sans text-2xl font-light text-white italic">
                        Connect Discord
                    </CardTitle>
                    <CardDescription className="text-white/70">
                        Enter your Discord token to control your rich presence
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {error && (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="discord-token" className="text-white/90">
                                Discord token
                            </Label>
                            <Input
                                id="discord-token"
                                type="password"
                                value={discordToken}
                                onChange={(e) =>
                                    setDiscordToken(e.target.value)
                                }
                                placeholder="Paste token"
                                className="border-white/30 bg-white/10 font-mono text-sm text-white placeholder:text-white/45 focus-visible:ring-[#47a6ff]/50"
                            />
                            <p className="text-xs text-white/55">
                                Found in Discord Developer Tools or browser
                                localStorage
                            </p>
                        </div>

                        <Button
                            type="submit"
                            disabled={loading}
                            className="w-full rounded-full border border-white/30 bg-[#47a6ff]/90 text-white hover:bg-[#47a6ff]"
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving…
                                </>
                            ) : (
                                "Continue"
                            )}
                        </Button>
                    </form>

                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <span className="w-full border-t border-white/15" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-black/50 px-2 text-white/50">
                                Or
                            </span>
                        </div>
                    </div>

                    <Button
                        type="button"
                        variant="outline"
                        onClick={handleSkip}
                        disabled={loading}
                        className="w-full rounded-full border-white/30 bg-transparent text-white hover:bg-white/10"
                    >
                        Skip for now
                    </Button>

                    <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-xs text-amber-100/90">
                        <strong className="text-amber-50">How to get your token</strong>
                        <ol className="mt-2 list-inside list-decimal space-y-1 text-amber-100/80">
                            <li>Open Discord in browser</li>
                            <li>Press F12 → Application → Local Storage</li>
                            <li>Find &quot;token&quot; under discord.com</li>
                        </ol>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
