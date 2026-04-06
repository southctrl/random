import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { headers } from "next/headers"
import { NextResponse } from "next/server"

const DISCORD_API_BASE = "https://discord.com/api/v10"

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
    const { token } = body

    if (!token) {
      return NextResponse.json(
        { error: "Token is required" },
        { status: 400 }
      )
    }

    try {
      console.log("🔍 [VALIDATE-TOKEN] Attempting to validate token with Discord API...")
      
      const authToken = token.startsWith("Bot ") ? token : `${token}`
      
      console.log("🔑 [VALIDATE-TOKEN] Token type:", token.startsWith("Bot ") ? "Bot token" : "User token")
      console.log("🔑 [VALIDATE-TOKEN] Authorization header:", authToken.substring(0, 30) + "...")
      
      const response = await fetch(`${DISCORD_API_BASE}/users/@me`, {
        headers: {
          Authorization: authToken,
        },
      })

      console.log(" [VALIDATE-TOKEN] Discord API response status:", response.status)
      console.log(" [VALIDATE-TOKEN] Discord API response headers:", Object.fromEntries(response.headers.entries()))

      if (!response.ok) {
        console.log(" [VALIDATE-TOKEN] Discord API rejected token - marking as invalid")
        await prisma.presenceSettings.update({
          where: { userId: session.user.id },
          data: {
            tokenIsValid: false,
            tokenLastValidatedAt: new Date(),
          },
        })

        return NextResponse.json({
          valid: false,
          error: "Token is invalid or expired",
          code: response.status
        })
      }

      const discordUser = await response.json()
      console.log(" [VALIDATE-TOKEN] Discord API accepted token - user:", discordUser.username)
      
      await prisma.presenceSettings.update({
        where: { userId: session.user.id },
        data: {
          tokenIsValid: true,
          tokenLastValidatedAt: new Date(),
        },
      })

      return NextResponse.json({
        valid: true,
        user: {
          id: discordUser.id,
          username: discordUser.username,
          discriminator: discordUser.discriminator,
          avatar: discordUser.avatar,
          global_name: discordUser.global_name,
        }
      })
    } catch (fetchError) {
      console.error(" [VALIDATE-TOKEN] Discord API fetch error:", fetchError)
      return NextResponse.json({
        valid: false,
        error: "Failed to validate token with Discord"
      })
    }
  } catch (err) {
    console.error("Validate token error:", err)
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
        tokenIsValid: true,
        tokenLastValidatedAt: true,
        discordTokenEncrypted: true,
      },
    })

    if (!settings || !settings.discordTokenEncrypted) {
      return NextResponse.json({
        hasToken: false,
        isValid: false,
        lastValidated: null
      })
    }

    return NextResponse.json({
      hasToken: true,
      isValid: settings.tokenIsValid,
      lastValidated: settings.tokenLastValidatedAt?.toISOString()
    })
  } catch (err) {
    console.error("Get token status error:", err)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
