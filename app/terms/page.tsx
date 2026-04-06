import Link from "next/link"

export default function Terms() {
    return (
        <main className="relative min-h-screen overflow-hidden">
            <div
                className="absolute inset-0"
                aria-hidden
                style={{
                    background:
                        "radial-gradient(ellipse 130% 90% at 50% 100%, #47a6ff 0%, #0a1628 45%, #000000 100%)",
                }}
            />
            <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-4xl flex-col px-6 py-16 sm:px-10">
                <div className="rounded-3xl border border-white/10 bg-black/35 p-8 backdrop-blur-xl sm:p-10">
                    <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                            <h1 className="text-3xl font-semibold text-white">Terms of Service</h1>
                            <p className="mt-2 text-sm text-white/55">
                                Last updated: {new Date().toLocaleDateString()}
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <Link
                                href="/"
                                className="inline-flex rounded-full border border-white/20 bg-white/5 px-4 py-2 text-sm text-white/80 backdrop-blur-sm transition-colors hover:bg-white/10"
                            >
                                Home
                            </Link>
                        </div>
                    </div>

                    <div className="mt-8 space-y-8 text-white/80">
                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">1. Acceptance</h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                By using Expel, you agree to these Terms. If you do not agree, do not use the service.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">2. What Expel does</h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                Expel lets you control Discord presence features (such as rich presence and custom status) via a local RPC bridge.
                                You are responsible for how you configure and use these features.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">3. Acceptable use</h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                You agree not to misuse the service, attempt to disrupt it, or use it in a way that violates Discord’s terms,
                                applicable law, or the rights of others.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">4. Availability</h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                The service is provided on an “as is” and “as available” basis. Features may change or be removed at any time.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">5. Disclaimer</h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                Expel does not guarantee uninterrupted or error-free operation. We are not responsible for issues caused by Discord,
                                your device, your network, or third-party services.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">6. Contact</h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                Questions about these terms? Use the contact form on the site.
                            </p>
                        </section>
                    </div>
                </div>
            </div>
        </main>
    )
}
