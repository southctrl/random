import { createAuthClient } from "better-auth/react"
import type { auth } from "@/lib/auth"
import { adminClient, inferAdditionalFields } from "better-auth/client/plugins"
import { apiKeyClient } from "@better-auth/api-key/client"

export const authClient = createAuthClient({
    baseURL: process.env.NEXT_PUBLIC_APP_URL || "https://beta.expel.best",
    plugins: [
        adminClient(),
        apiKeyClient(),
        inferAdditionalFields<typeof auth>(),
    ],
})
