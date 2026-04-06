import Link from "next/link"

export default function Privacy() {
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
                            <h1 className="text-3xl font-semibold text-white">
                                Privacy Policy
                            </h1>
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

                    <div className="mt-8 space-y-8">
                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">
                                1. What we collect
                            </h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                Expel stores basic account and session information used to
                                sign you in (for example, email and profile image if
                                provided by your auth provider). If you use the dashboard
                                panels, Expel may store your saved configuration (such as
                                rich presence fields or custom status text) so it can be
                                restored when you return.
                            </p>
                            <p className="text-sm leading-relaxed text-white/70">
                                Discord tokens are stored locally on your device (in your
                                browser) and are used to authorize requests to your RPC
                                bridge. Expel does not store Discord tokens in our
                                database.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">
                                2. How we use information
                            </h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                We use the information to:
                            </p>
                            <div className="mt-2 space-y-1 text-sm text-white/70">
                                <div>
                                    - Authenticate you and keep you signed in
                                </div>
                                <div>
                                    - Save and restore your dashboard settings
                                </div>
                                <div>
                                    - Provide basic operational logging for reliability and debugging
                                </div>
                            </div>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">
                                3. Sharing
                            </h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                We do not sell your personal information.
                            </p>
                            <p className="text-sm leading-relaxed text-white/70">
                                We do not share user data with third parties except where
                                necessary to operate the service (for example, database
                                hosting). When you enable presence features, your Discord
                                client and Discord’s APIs will process the data needed to
                                display your status.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">
                                4. Retention
                            </h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                We keep data only as long as needed to provide the service
                                and maintain security. You can clear saved settings by
                                overwriting them from the dashboard.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">
                                5. Security
                            </h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                We use reasonable safeguards to protect data, including
                                protecting data in transit where supported by your
                                connection. Sensitive credentials (like Discord tokens)
                                are not stored in our database, but no system is 100%
                                secure.
                            </p>
                        </section>

                        <section className="space-y-2">
                            <h2 className="text-lg font-semibold text-white">
                                6. Contact
                            </h2>
                            <p className="text-sm leading-relaxed text-white/70">
                                If you have questions about privacy, use the contact form
                                on the site.
                            </p>
                        </section>
                    </div>
                </div>
            </div>
        </main>
    )
}
