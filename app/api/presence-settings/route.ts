import { NextRequest, NextResponse } from "next/server"
import { headers } from "next/headers"
import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"

export const runtime = "nodejs"

function getDeviceInfo(req: NextRequest) {
    const userAgent = req.headers.get("user-agent") || "unknown"
    const forwarded = req.headers.get("x-forwarded-for")
    const ip = forwarded ? forwarded.split(",")[0] : req.headers.get("x-real-ip") || "unknown"
    
    let deviceType = "desktop"
    if (userAgent.includes("Mobile") || userAgent.includes("Android") || userAgent.includes("iPhone")) {
        deviceType = "mobile"
    } else if (userAgent.includes("Tablet") || userAgent.includes("iPad")) {
        deviceType = "tablet"
    }
    
    const deviceId = `${deviceType}-${userAgent.slice(0, 50).replace(/[^a-zA-Z0-9]/g, "")}-${ip.slice(0, 10)}`
    
    return {
        deviceId: deviceId.toLowerCase(),
        deviceType,
        userAgent,
        ip
    }
}

export async function GET(req: NextRequest) {
    const session = await auth.api.getSession({ headers: await headers() })
    if (!session?.user?.id) {
        return NextResponse.json({ error: "unauthorized" }, { status: 401 })
    }

    if (!(prisma as unknown as { presenceSettings?: unknown }).presenceSettings) {
        return NextResponse.json(
            {
                error: "database-out-of-date",
                detail: "Database is out of data run npx prisma generate & npx prisma db push.",
            },
            { status: 500 }
        )
    }

    const { deviceId } = getDeviceInfo(req)
    const url = new URL(req.url)
    const lastSync = url.searchParams.get('lastSync')

    const row = await (prisma as any).presenceSettings.findUnique({
        where: { userId: session.user.id },
        select: { 
            rich: true, 
            custom: true, 
            spotify: true,
            lastDevice: true,
            lastSyncedAt: true,
            updatedAt: true
        },
    })

    let needsSync = true
    if (lastSync && row?.lastSyncedAt) {
        const lastSyncDate = new Date(lastSync)
        const serverSyncDate = new Date(row.lastSyncedAt)
        needsSync = serverSyncDate > lastSyncDate
    }

    return NextResponse.json({
        rich: row?.rich ?? null,
        custom: row?.custom ?? null,
        spotify: row?.spotify ?? null,
        lastDevice: row?.lastDevice || null,
        lastSyncedAt: row?.lastSyncedAt || null,
        needsSync,
        currentDevice: deviceId
    })
}

export async function POST(req: NextRequest) {
    const session = await auth.api.getSession({ headers: await headers() })
    if (!session?.user?.id) {
        return NextResponse.json({ error: "unauthorized" }, { status: 401 })
    }

    if (!(prisma as unknown as { presenceSettings?: unknown }).presenceSettings) {
        return NextResponse.json(
            {
                error: "database-out-of-date",
                detail: "Database is out of data run npx prisma generate & npx prisma db push.",
            },
            { status: 500 }
        )
    }

    const body = (await req.json().catch(() => null)) as unknown
    if (!body || typeof body !== "object") {
        return NextResponse.json({ error: "invalid_body" }, { status: 400 })
    }

    const { rich, custom, spotify, clientTimestamp, force } = body as {
        rich?: unknown
        custom?: unknown
        spotify?: unknown
        clientTimestamp?: string
        force?: boolean
    }

    const { deviceId } = getDeviceInfo(req)
    const now = new Date()

    const existing = await (prisma as any).presenceSettings.findUnique({
        where: { userId: session.user.id },
        select: { lastDevice: true, lastSyncedAt: true, updatedAt: true }
    })

    let conflict = false
    if (existing && existing.lastDevice && existing.lastDevice !== deviceId && !force) {
        const serverTime = new Date(existing.lastSyncedAt || existing.updatedAt)
        const clientTime = clientTimestamp ? new Date(clientTimestamp) : new Date(0)
        
        if (serverTime > clientTime) {
            conflict = true
            return NextResponse.json({
                error: "sync_conflict",
                message: "Settings were updated on another device",
                lastDevice: existing.lastDevice,
                serverTime: serverTime.toISOString(),
                needsRefresh: true
            }, { status: 409 })
        }
    }

    await (prisma as any).presenceSettings.upsert({
        where: { userId: session.user.id },
        create: {
            userId: session.user.id,
            rich: rich ?? undefined,
            custom: custom ?? undefined,
            spotify: spotify ?? undefined,
            lastDevice: deviceId,
            lastSyncedAt: now,
        },
        update: {
            rich: rich ?? undefined,
            custom: custom ?? undefined,
            spotify: spotify ?? undefined,
            lastDevice: deviceId,
            lastSyncedAt: now,
        },
    })

    return NextResponse.json({ 
        message: "saved",
        deviceId,
        syncedAt: now.toISOString(),
        conflict: false
    })
}
