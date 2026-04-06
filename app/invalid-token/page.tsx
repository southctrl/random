"use client"

import { Button } from "@/components/ui/button"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

export default function InvalidTokenPage() {
    const router = useRouter()

    const handleRetry = () => {
        if (typeof window !== "undefined") {
            localStorage.removeItem("discord_token")
            localStorage.removeItem("discord_token_validated")
        }
        router.push("/onboarding")
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-background p-4">
            <Card className="w-full max-w-md border-destructive/50">
                <CardHeader className="space-y-4 text-center">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
                        <AlertTriangle className="h-8 w-8 text-destructive" />
                    </div>
                    <CardTitle className="text-2xl font-bold text-destructive">
                        Invalid Token
                    </CardTitle>
                    <CardDescription className="text-base">
                        Invalid token or your token has been reset, double check
                        and then try again!
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2 rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
                        <p className="font-medium text-foreground">
                            This can happen when:
                        </p>
                        <ul className="list-inside list-disc space-y-1">
                            <li>Your Discord bot token was regenerated</li>
                            <li>The token was revoked or expired</li>
                            <li>You entered an incorrect token</li>
                            <li>Your account permissions changed</li>
                        </ul>
                    </div>

                    <div className="flex flex-col gap-3">
                        <Button
                            onClick={handleRetry}
                            className="w-full"
                            size="lg"
                        >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Enter New Token
                        </Button>

                        <Button
                            variant="outline"
                            asChild
                            className="w-full"
                            size="lg"
                        >
                            <Link href="/login">
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Back to Login
                            </Link>
                        </Button>
                    </div>

                    <p className="pt-2 text-center text-xs text-muted-foreground">
                        Need help? Check the{" "}
                        <a
                            href="https://discord.com/developers/docs"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
                        >
                            Discord Developer Portal
                        </a>{" "}
                        to regenerate your token.
                    </p>
                </CardContent>
            </Card>
        </div>
    )
}
