"use client"

import { useState, useEffect } from "react"
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
import { Loader2 } from "lucide-react"

export default function LoginPage() {
    const router = useRouter()
    const { data: sessionData, isPending } = authClient.useSession()
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (isPending) return
        if (sessionData?.session) {
            const discordToken = localStorage.getItem("discord_token")
            if (discordToken) {
                router.replace("/dashboard")
            } else {
                router.replace("/onboarding")
            }
        }
    }, [isPending, sessionData, router])

    const handleDiscordSignIn = async () => {
        setLoading(true)
        setError(null)
        try {
            await authClient.signIn.social({
                provider: "discord",
                callbackURL: "/onboarding",
            })
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to sign in with Discord"
            )
            setLoading(false)
        }
    }

    if (isPending) {
        return (
            <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
                <BrandedBackground />
                <Loader2
                    className="relative z-10 h-10 w-10 animate-spin text-white/80"
                    aria-label="Loading"
                />
            </div>
        )
    }

    if (sessionData?.session) {
        return (
            <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
                <BrandedBackground />
                <Loader2
                    className="relative z-10 h-10 w-10 animate-spin text-white/80"
                    aria-label="Redirecting"
                />
            </div>
        )
    }

    return (
        <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
            <BrandedBackground />
            <Card className="relative z-10 w-full max-w-md border-white/20 bg-black/35 text-white shadow-xl backdrop-blur-md">
                <CardHeader className="space-y-1">
                    <p className="font-sans text-xs font-light tracking-[0.2em] text-white/60 uppercase">
                        Welcome
                    </p>
                    <CardTitle className="font-sans text-2xl font-light text-white italic">
                        Sign in
                    </CardTitle>
                    <CardDescription className="text-white/70">
                        Sign in with Discord to continue
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {error && (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                            {error}
                        </div>
                    )}

                    <Button
                        onClick={handleDiscordSignIn}
                        disabled={loading}
                        className="w-full rounded-full border border-white/30 bg-[#47a6ff]/90 text-white hover:bg-[#47a6ff]"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Signing in…
                            </>
                        ) : (
                            "Sign in with Discord"
                        )}
                    </Button>
                </CardContent>
            </Card>
        </div>
    )
}
