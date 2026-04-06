async function deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
  const encoder = new TextEncoder()
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveKey"]
  )

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: salt as BufferSource,
      iterations: 100000,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  )
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ""
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}

export interface EncryptedData {
  ciphertext: string
  iv: string
  salt: string
}

export async function encryptToken(
  token: string,
  userId: string
): Promise<EncryptedData> {
  const encoder = new TextEncoder()

  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))

  const key = await deriveKey(userId, salt)

  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    encoder.encode(token)
  )

  return {
    ciphertext: arrayBufferToBase64(ciphertext),
    iv: arrayBufferToBase64(iv.buffer),
    salt: arrayBufferToBase64(salt.buffer),
  }
}

export async function decryptToken(
  encryptedData: EncryptedData,
  userId: string
): Promise<string> {
  const decoder = new TextDecoder()

  const ciphertext = base64ToArrayBuffer(encryptedData.ciphertext)
  const iv = new Uint8Array(base64ToArrayBuffer(encryptedData.iv))
  const salt = new Uint8Array(base64ToArrayBuffer(encryptedData.salt))

  const key = await deriveKey(userId, salt)

  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    ciphertext
  )

  return decoder.decode(plaintext)
}

export function isEncrypted(value: string): boolean {
  return value.length > 100 && /^[A-Za-z0-9+/=]+$/.test(value)
}