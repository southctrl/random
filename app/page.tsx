"use client"
import { useState, useSyncExternalStore } from "react"
import { NeuroNoise } from "@paper-design/shaders-react"
import { LiquidMetalButton } from "@/components/v0/liquid-metal-button"
import { Footer } from "@/components/layout/Footer"


function subscribePrefersReducedMotion(onStoreChange: () => void) {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    mq.addEventListener("change", onStoreChange)
    return () => mq.removeEventListener("change", onStoreChange)
}

function getPrefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

function usePrefersReducedMotion() {
    return useSyncExternalStore(
        subscribePrefersReducedMotion,
        getPrefersReducedMotion,
        () => false
    )
}

const NEURO_NOISE_MAX_PIXELS = 1280 * 720

export default function Home() {
    const prefersReducedMotion = usePrefersReducedMotion()
    const [email, setEmail] = useState("")
    const [status, setStatus] = useState<
        "idle" | "loading" | "success" | "error"
    >("idle")

    const handleSubmit = async () => {
        if (!email) return
        setStatus("loading")
        try {
            const res = await fetch("/api/contact", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email }),
            })
            if (!res.ok) throw new Error()
            setStatus("success")
            setEmail("")
        } catch {
            setStatus("error")
        }
    }
    return (
        <main className="relative flex min-h-screen flex-col overflow-hidden">
            <div className="absolute inset-0">
                {prefersReducedMotion ? (
                    <div
                        className="h-full w-full"
                        style={{
                            background:
                                "radial-gradient(ellipse 130% 90% at 50% 100%, #47a6ff 0%, #0a1628 45%, #000000 100%)",
                        }}
                        aria-hidden
                    />
                ) : (
                    <NeuroNoise
                        style={{ height: "100%", width: "100%" }}
                        colorFront="#ffffff"
                        colorMid="#47a6ff"
                        colorBack="#000000"
                        brightness={0.13}
                        contrast={1}
                        speed={0.5}
                        scale={0.72}
                        rotation={76}
                        minPixelRatio={1}
                        maxPixelCount={NEURO_NOISE_MAX_PIXELS}
                    />
                )}
            </div>

            <div className="relative z-10 flex flex-1 items-center justify-center px-8">
                <div className="w-full max-w-2xl space-y-8 text-center">
                    <h1 className="font-sans text-6xl font-light text-white italic md:text-7xl">
                        Coming Soon
                    </h1>

                    <div className="relative">
                        <input
                            type="email"
                            placeholder="Enter your email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full rounded-full border border-white/30 bg-white/20 px-6 py-4 pr-32 text-lg text-white placeholder-white/70 backdrop-blur-sm transition-all duration-300 focus:border-white/50 focus:ring-2 focus:ring-white/50 focus:outline-none"
                        />
                        <div className="absolute top-1/2 right-2 -translate-y-1/2">
                            <LiquidMetalButton
                                viewMode="icon"
                                onClick={handleSubmit}
                            />
                        </div>
                    </div>
                    {status === "success" && (
                        <p className="text-sm text-green-400">
                            Thanks for subscribing!
                        </p>
                    )}
                    {status === "error" && (
                        <p className="text-sm text-red-400">
                            Something went wrong. Try again.
                        </p>
                    )}

                    <p className="font-sans text-lg leading-relaxed font-light text-white/90">
                        Don&apos;t miss out on the platform&apos;s release!
                        <br />
                        Sign up for our newsletter now and stay in the loop.
                    </p>
                </div>
            </div>

            <div className="relative z-10">
                <Footer />
            </div>
        </main>
    )
}
