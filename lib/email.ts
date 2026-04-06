import { Resend } from "resend"


const apiKey = process.env.RESEND_API_KEY
if (!apiKey) {
    throw new Error("RESEND_API_KEY environment variable is not set")
    }

const resend = new Resend(apiKey)

export async function addContact(email: string) {
    return await resend.contacts.create({
        email,
        unsubscribed: false,
    })
}
