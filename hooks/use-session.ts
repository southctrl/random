"use client"

import { useState, useEffect } from "react"
import { authClient } from "@/lib/auth-client"

type Session = {
    user: {
        id: string
        email: string
        name?: string | null
        image?: string | null
    }
    session: {
        token: string
        expiresAt: number
    }
}

export function useSession() {
    const [session, setSession] = useState<Session | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        authClient.getSession().then((result) => {
            if (result.data?.session) {
                setSession({
                    user: result.data.user,
                    session: {
                        token: result.data.session.token,
                        expiresAt: result.data.session.expiresAt.getTime(),
                    },
                } as Session)
            }
            setIsLoading(false)
        })
    }, [])

    return { data: session, isLoading } as {
        data: Session | null
        isLoading: boolean
    }
}
