import { prismaAdapter } from "better-auth/adapters/prisma"
import { prisma } from "./prisma"
import { admin, bearer } from "better-auth/plugins"
import { apiKey } from "@better-auth/api-key"
import { nextCookies } from "better-auth/next-js"
import { betterAuth } from "better-auth"

export const auth = betterAuth({
    database: prismaAdapter(prisma, {
        provider: "postgresql",
    }),
    emailAndPassword: {
        enabled: false,
    },
    socialProviders: {
        discord: {
            clientId: process.env.DISCORD_CLIENT_ID!,
            clientSecret: process.env.DISCORD_CLIENT_SECRET!,
        },
    },
    plugins: [
        bearer(), 
        apiKey(), 
        admin(), 
        nextCookies()
    ],
})
