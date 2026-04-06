import { NextRequest, NextResponse } from "next/server"

const API_BASE = process.env.RPC_API_URL || "http://localhost:8000"

async function proxy(request: NextRequest, path: string[]) {
    const pathStr = path.join("/")
    const url = `${API_BASE}/${pathStr}${request.nextUrl.search}`

    const authHeader = request.headers.get("authorization")
    const contentType = request.headers.get("content-type")

    const headers: Record<string, string> = {}
    if (authHeader) headers["Authorization"] = authHeader
    if (contentType) headers["Content-Type"] = contentType

    let body: ArrayBuffer | undefined
    if (request.method !== "GET" && request.method !== "HEAD") {
        const buf = await request.arrayBuffer()
        body = buf.byteLength ? buf : undefined
    }

    const response = await fetch(url, {
        method: request.method,
        headers,
        body: body ? new Uint8Array(body) : undefined,
    })

    const resContentType = response.headers.get("content-type")
    if (resContentType?.includes("application/json")) {
        const data = await response
            .json()
            .catch(() => ({ error: "Invalid JSON response" }))
        if ((data as { error?: string })?.error === "client not logged in") {
            ;(data as { error?: string }).error = "login first!"
        }
        return NextResponse.json(data, { status: response.status })
    }

    const text = await response.text()
    return NextResponse.json(
        {
            error: "Backend returned non-JSON response",
            status: response.status,
            details: text,
        },
        { status: response.status }
    )
}

export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    try {
        const { path } = await params
        return await proxy(request, path)
    } catch (error) {
        return NextResponse.json(
            {
                error: "Failed to proxy request",
                details: error instanceof Error ? error.message : String(error),
            },
            { status: 500 }
        )
    }
}

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    try {
        const { path } = await params
        return await proxy(request, path)
    } catch (error) {
        return NextResponse.json(
            {
                error: "Failed to proxy request",
                details: error instanceof Error ? error.message : String(error),
            },
            { status: 500 }
        )
    }
}
