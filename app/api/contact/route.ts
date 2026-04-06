import { NextResponse } from "next/server"
import { addContact } from "@/lib/email"

export async function POST(request: Request) {
    try {
        const { email } = await request.json()
        if (!email) {
            return NextResponse.json(
                { error: "Email is required" },
                { status: 400 }
            )
        }
        await addContact(email)
        return NextResponse.json({ success: true })
    } catch (error) {
        console.error("Failed to add contact:", error)
        return NextResponse.json(
            { error: "Failed to add contact" },
            { status: 500 }
        )
    }
}
