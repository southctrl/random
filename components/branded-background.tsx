export function BrandedBackground({ className }: { className?: string }) {
    return (
        <div
            className={className ?? "pointer-events-none absolute inset-0 -z-10"}
            aria-hidden
            style={{
                background:
                    "radial-gradient(ellipse 130% 90% at 50% 100%, #47a6ff 0%, #0a1628 45%, #000000 100%)",
            }}
        />
    )
}
