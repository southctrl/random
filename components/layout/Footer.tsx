export function Footer() {
    return (
        <footer className="border-t border-white/10 bg-black/20 backdrop-blur-sm">
            <div className="container mx-auto px-4 py-6">
                <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
                    <p className="text-sm text-white/55">
                        © {new Date().getFullYear()} Expel. All rights reserved.
                    </p>
                    <div className="flex gap-4">
                        <a
                            href="/privacy"
                            className="text-sm text-white/55 hover:text-white"
                        >
                            Privacy
                        </a>
                        <a
                            href="/terms"
                            className="text-sm text-white/55 hover:text-white"
                        >
                            Terms
                        </a>
                        <a

                            href="/dashboard"
                            className="text-sm text-white/55 hover:text-blue-500"
                        >   
                            Dashboard 
                        </ a>
                    </div>
                </div>
            </div>
        </footer>
    )
}
