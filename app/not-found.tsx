import Link from "next/link"

export default function NotFound() {
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
            <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-8 text-center">
                <p className="font-sans text-sm font-light tracking-[0.2em] text-white/60 uppercase">
                    Error
                </p>
                <h1 className="mt-2 font-sans text-7xl font-light text-white italic md:text-8xl">
                    404
                </h1>
                <p className="mt-8 max-w-md font-sans text-lg font-light leading-relaxed text-white/90">
                    Sorry, the page you were looking for was not found.
                </p>
                <Link
                    href="/"
                    className="mt-10 inline-flex rounded-full border border-white/30 bg-white/20 px-8 py-3 text-base font-light text-white backdrop-blur-sm transition-all duration-300 hover:border-white/50 hover:bg-white/25 focus-visible:ring-2 focus-visible:ring-white/50 focus-visible:outline-none"
                >
                    Go home
                </Link>
            </div>
        </main>
    )
}
