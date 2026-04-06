"use client"

import Link from "next/link"
import { authClient } from "@/lib/auth-client"
import { Button } from "@/components/ui/button"
import { useSession } from "@/hooks/use-session"

export function Navbar() {
    const { data: session, isLoading } = useSession()

    return (
        <nav className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container mx-auto flex h-16 items-center justify-between px-4">
                <Link href="/" className="flex items-center space-x-2">
                    <span className="text-xl font-bold">Expel</span>
                </Link>

                <div className="flex items-center gap-4">
                    {isLoading ? null : session ? (
                        <>
                            <span className="text-sm text-muted-foreground">
                                {session.user.name || session.user.email}
                            </span>
                            <Button asChild variant="outline" size="sm">
                                <Link href="/dashboard">Dashboard</Link>
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => authClient.signOut()}
                            >
                                Sign Out
                            </Button>
                        </>
                    ) : (
                        <Button asChild size="sm">
                            <Link href="/login">Sign In</Link>
                        </Button>
                    )}
                </div>
            </div>
        </nav>
    )
}
