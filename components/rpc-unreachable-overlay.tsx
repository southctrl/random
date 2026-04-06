"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"

function WifiStrengthAnimation({ className }: { className?: string }) {
    const [phase, setPhase] = useState(0)

    useEffect(() => {
        const id = setInterval(() => {
            setPhase((p) => (p + 1) % 4)
        }, 520)
        return () => clearInterval(id)
    }, [])

    const barHeightsPx = [7, 12, 17, 22]
    const dim = 0.22
    const lit = 1

    return (
        <div
            className={className}
            role="img"
            aria-label="Signal strength animation"
        >
            <div className="flex flex-col items-center">
                <div className="flex h-[26px] items-end justify-center gap-[7px]">
                    {barHeightsPx.map((h, i) => (
                        <span
                            key={i}
                            className="w-[5px] bg-white transition-opacity duration-[280ms] ease-out"
                            style={{
                                height: h,
                                borderRadius: 9999,
                                opacity: i <= phase ? lit : dim,
                            }}
                        />
                    ))}
                </div>

                <svg
                    className="mt-[14px] text-white"
                    width={64}
                    height={32}
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden
                >
                    <path
                        stroke="currentColor"
                        strokeWidth="1.75"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M1.924 8.674a13.25 13.25 0 0 1 20.152 0"
                        opacity={phase >= 1 ? 0.95 : dim}
                    />
                    <path
                        stroke="currentColor"
                        strokeWidth="1.75"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5.106 11.856a9.25 9.25 0 0 1 13.788 0"
                        opacity={phase >= 2 ? 0.95 : dim}
                    />
                    <path
                        stroke="currentColor"
                        strokeWidth="1.75"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M8.288 15.038a5.25 5.25 0 0 1 7.424 0"
                        opacity={phase >= 3 ? 0.95 : dim}
                    />
                </svg>
            </div>
        </div>
    )
}

type RpcUnreachableOverlayProps = {
    onRetry: () => void | Promise<void>
    retrying?: boolean
}

export function RpcUnreachableOverlay({
    onRetry,
    retrying,
}: RpcUnreachableOverlayProps) {
    return (
        <div
            className="fixed inset-0 z-[200] flex min-h-screen flex-col items-center justify-center bg-black/50 px-6 py-12 backdrop-blur-2xl"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="rpc-unreachable-title"
            aria-describedby="rpc-unreachable-desc"
        >
            <div className="flex w-full max-w-md flex-col items-center text-center">
                <WifiStrengthAnimation className="mb-10 flex flex-col items-center text-white" />
                <h2
                    id="rpc-unreachable-title"
                    className="text-xl font-semibold tracking-tight text-white sm:text-2xl"
                >
                    Disconnected
                </h2>
                <p
                    id="rpc-unreachable-desc"
                    className="mt-3 text-base font-light leading-relaxed text-white/60"
                >
                    Trying to reconnect…
                </p>
                {retrying && (
                    <p className="mt-4 flex items-center justify-center gap-2 text-sm text-[#7ec8ff]">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Checking connection
                    </p>
                )}
                <Button
                    type="button"
                    variant="outline"
                    disabled={retrying}
                    onClick={() => void onRetry()}
                    className="mt-10 rounded-full border-sky-500/25 bg-sky-500/10 px-8 text-white/90 hover:border-sky-400/40 hover:bg-sky-500/20"
                >
                    {retrying ? "Reconnecting…" : "Retry now"}
                </Button>
            </div>
        </div>
    )
}
