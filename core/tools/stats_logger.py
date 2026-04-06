import httpx

NEXT_URL = "http://localhost:8000/api/internal/log-command"
INTERNAL_SECRET = "e294750d45901ee598707b92204dcd87805bb267f788b083ed2cee0c0b6d18f5"

async def log_command(discord_id: str, command: str):
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(NEXT_URL, json={
                "discord_id": discord_id,
                "command": command,
            }, headers={"x-internal-secret": INTERNAL_SECRET})
    except Exception:
        pass
