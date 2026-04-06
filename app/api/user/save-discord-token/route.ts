import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { headers } from "next/headers"
import { NextResponse } from "next/server"

export async function POST(request: Request) {
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

    const body = await request.json()
    const { encryptedToken, iv, salt } = body

    if (!encryptedToken || !iv) {
      return NextResponse.json(
        { error: "Missing encrypted token or IV" },
        { status: 400 }
      )
    }

    const userAgent = request.headers.get("user-agent") || "unknown"
    const deviceInfo = userAgent.substring(0, 255)

    await prisma.presenceSettings.upsert({
      where: { userId: session.user.id },
      update: {
        discordTokenEncrypted: encryptedToken,
        discordTokenIv: `${iv}:${salt}`,
        tokenIsValid: true,
        tokenLastValidatedAt: new Date(),
        lastDevice: deviceInfo,
        lastSyncedAt: new Date(),
      },
      create: {
        userId: session.user.id,
        discordTokenEncrypted: encryptedToken,
        discordTokenIv: `${iv}:${salt}`,
        tokenIsValid: true,
        tokenLastValidatedAt: new Date(),
        lastDevice: deviceInfo,
        lastSyncedAt: new Date(),
      },
    })

    return NextResponse.json({ 
      success: true,
      message: "Token saved and will sync across devices"
    })
  } catch (err) {
    console.error("Save token error:", err)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

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

    const settings = await prisma.presenceSettings.findUnique({
      where: { userId: session.user.id },
      select: {
        discordTokenEncrypted: true,
        discordTokenIv: true,
        tokenIsValid: true,
        tokenLastValidatedAt: true,
      },
    })

    if (!settings || !settings.discordTokenEncrypted) {
      return NextResponse.json({ 
        hasToken: false,
        token: null
      })
    }

    const [iv, salt] = (settings.discordTokenIv || "").split(":")

    return NextResponse.json({
      hasToken: true,
      encryptedToken: settings.discordTokenEncrypted,
      iv,
      salt,
      isValid: settings.tokenIsValid,
      lastValidated: settings.tokenLastValidatedAt?.toISOString()
    })
  } catch (err) {
    console.error("Get token error:", err)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

export async function DELETE() {
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

    await prisma.presenceSettings.update({
      where: { userId: session.user.id },
      data: {
        discordTokenEncrypted: null,
        discordTokenIv: null,
        tokenIsValid: false,
        tokenLastValidatedAt: null,
      },
    })

    return NextResponse.json({ 
      success: true,
      message: "Token deleted"
    })
  } catch (err) {
    console.error("Delete token error:", err)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
