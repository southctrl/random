import { NextRequest, NextResponse } from "next/server"
import { headers } from "next/headers"
import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"

export const runtime = "nodejs"

export async function POST(req: NextRequest) {
    const session = await auth.api.getSession({ headers: await headers() })
    if (!session?.user?.id) {
        return NextResponse.json({ error: "unauthorized" }, { status: 401 })
    }

    const body = (await req.json().catch(() => null)) as unknown
    if (!body || typeof body !== "object") {
        return NextResponse.json({ error: "invalid_body" }, { status: 400 })
    }

    const { action, deviceId } = body as {
        action: "force_sync" | "get_server_state" | "mark_conflict_resolved"
        deviceId?: string
    }

    if (action === "get_server_state") {
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

        return NextResponse.json({
            serverState: {
                rich: row?.rich ?? null,
                custom: row?.custom ?? null,
                spotify: row?.spotify ?? null,
            },
            lastDevice: row?.lastDevice || null,
            lastSyncedAt: row?.lastSyncedAt || null,
        })
    }

    if (action === "force_sync" && deviceId) {
        const now = new Date()
        
        await (prisma as any).presenceSettings.update({
            where: { userId: session.user.id },
            data: {
                lastDevice: deviceId,
                lastSyncedAt: now,
            },
        })

        return NextResponse.json({
            message: "sync_forced",
            deviceId,
            syncedAt: now.toISOString(),
        })
    }

    if (action === "mark_conflict_resolved") {
        await (prisma as any).presenceSettings.update({
            where: { userId: session.user.id },
            data: {
                lastSyncedAt: new Date(),
            },
        })

        return NextResponse.json({ message: "conflict_resolved" })
    }

    return NextResponse.json({ error: "invalid_action" }, { status: 400 })
}

export async function GET(req: NextRequest) {
    const session = await auth.api.getSession({ headers: await headers() })
    if (!session?.user?.id) {
        return NextResponse.json({ error: "unauthorized" }, { status: 401 })
    }

    const url = new URL(req.url)
    const deviceId = url.searchParams.get('deviceId')

    if (!deviceId) {
        return NextResponse.json({ error: "device_id_required" }, { status: 400 })
    }

    const row = await (prisma as any).presenceSettings.findUnique({
        where: { userId: session.user.id },
        select: { 
            lastDevice: true,
            lastSyncedAt: true,
            updatedAt: true
        },
    })

    const isCurrentDevice = row?.lastDevice === deviceId
    const lastSyncTime = row?.lastSyncedAt || row?.updatedAt

    return NextResponse.json({
        isCurrentDevice,
        lastSyncTime,
        hasNewerData: lastSyncTime ? new Date(lastSyncTime) > new Date(url.searchParams.get('lastSync') || 0) : false,
    })
}
