import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { headers } from "next/headers"
import { NextResponse } from "next/server"

export async function GET() {
  try {
    const session = await auth.api.getSession({
      headers: await headers(),
    })
    
    if (!session?.user) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      )
    }

    let settings = await prisma.presenceSettings.findUnique({
      where: { userId: session.user.id },
    })

    if (!settings) {
      settings = await prisma.presenceSettings.create({
        data: { userId: session.user.id },
      })
    }

    return NextResponse.json({ 
      settings: {
        id: settings.id,
        user_id: settings.userId,
        discord_token_encrypted: settings.discordTokenEncrypted,
        discord_token_iv: settings.discordTokenIv,
        rpc_enabled: settings.rpcEnabled,
        rpc_type: settings.rpcType,
        custom_rpc_settings: settings.custom || {},
        game_rpc_settings: settings.rich || {},
        app_settings: settings.appSettings || {},
        token_is_valid: settings.tokenIsValid,
        token_last_validated_at: settings.tokenLastValidatedAt?.toISOString() || null,
        last_device: settings.lastDevice,
        last_synced_at: settings.lastSyncedAt?.toISOString() || null,
        created_at: settings.createdAt.toISOString(),
        updated_at: settings.updatedAt.toISOString(),
      }
    })
  } catch (err) {
    console.error("Get settings error:", err)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

export async function PATCH(request: Request) {
  try {
    console.log("[SETTINGS API] PATCH request received")
    
    const session = await auth.api.getSession({
      headers: await headers(),
    })
    
    console.log("[SETTINGS API] Session:", session?.user?.id ? `User ${session.user.id}` : "No session")
    
    if (!session?.user) {
      console.log("[SETTINGS API] Unauthorized - no session")
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      )
    }

    const body = await request.json()
    console.log("[SETTINGS API] Request body:", body)
    
    const allowedFields = [
      "rpc_enabled",
      "rpc_type",
      "custom_rpc_settings",
      "game_rpc_settings",
      "app_settings",
    ]

    const updates: Record<string, unknown> = {}
    
    if (body.rpc_enabled !== undefined) updates.rpcEnabled = body.rpc_enabled
    if (body.rpc_type !== undefined) updates.rpcType = body.rpc_type
    if (body.custom_rpc_settings !== undefined) updates.custom = body.custom_rpc_settings
    if (body.game_rpc_settings !== undefined) updates.rich = body.game_rpc_settings
    if (body.app_settings !== undefined) updates.appSettings = body.app_settings

    console.log("[SETTINGS API] Processed updates:", updates)

    const hasUpdates = Object.keys(updates).some(k => allowedFields.includes(k) || ["rpcEnabled", "rpcType", "custom", "rich", "appSettings"].includes(k))
    
    if (!hasUpdates) {
      console.log("[SETTINGS API] No valid fields to update")
      return NextResponse.json(
        { error: "No valid fields to update" },
        { status: 400 }
      )
    }

    const userAgent = request.headers.get("user-agent") || "unknown"
    updates.lastDevice = userAgent.substring(0, 255)
    updates.lastSyncedAt = new Date()

    const sanitizeData = (obj: any): any => {
      if (typeof obj === 'string') {
        return obj.replace(/[\u{1F600}-\u{1F64F}]|[\u{1F300}-\u{1F5FF}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu, '')
      }
      if (obj instanceof Date) {
        return obj
      }
      if (Array.isArray(obj)) {
        return obj.map(sanitizeData)
      }
      if (obj && typeof obj === 'object') {
        const sanitized: any = {}
        for (const [key, value] of Object.entries(obj)) {
          sanitized[key] = sanitizeData(value)
        }
        return sanitized
      }
      return obj
    }

    const sanitizedUpdates = sanitizeData(updates)

    console.log("[SETTINGS API] Final updates with metadata:", sanitizedUpdates)

    const settings = await prisma.presenceSettings.upsert({
      where: { userId: session.user.id },
      update: sanitizedUpdates,
      create: {
        userId: session.user.id,
        ...sanitizedUpdates,
      },
    })

    console.log("[SETTINGS API] Settings updated successfully:", settings.id)

    return NextResponse.json({ 
      success: true,
      settings: {
        id: settings.id,
        user_id: settings.userId,
        rpc_enabled: settings.rpcEnabled,
        rpc_type: settings.rpcType,
        last_synced_at: settings.lastSyncedAt?.toISOString(),
      }
    })
  } catch (err) {
    console.error("[SETTINGS API] Update settings error:", err)
    console.error("[SETTINGS API] Error stack:", err instanceof Error ? err.stack : "No stack trace")
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Internal server error" },
      { status: 500 }
    )
  }
}
