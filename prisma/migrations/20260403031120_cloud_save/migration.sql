-- CreateTable
CREATE TABLE "presence_settings" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "rich" JSONB,
    "custom" JSONB,
    "spotify" JSONB,
    "discordTokenEncrypted" TEXT,
    "discordTokenIv" TEXT,
    "tokenIsValid" BOOLEAN NOT NULL DEFAULT false,
    "tokenLastValidatedAt" TIMESTAMP(3),
    "rpcEnabled" BOOLEAN NOT NULL DEFAULT true,
    "rpcType" TEXT NOT NULL DEFAULT 'rich',
    "appSettings" JSONB,
    "lastDevice" TEXT,
    "lastSyncedAt" TIMESTAMP(3),
    "deviceMetadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "presence_settings_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "presence_settings_userId_key" ON "presence_settings"("userId");

-- AddForeignKey
ALTER TABLE "presence_settings" ADD CONSTRAINT "presence_settings_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE ON UPDATE CASCADE;
