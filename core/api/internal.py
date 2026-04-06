import logging, config
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

logger = logging.getLogger(__name__)

internal = APIRouter()

INTERNAL_SECRET = config.Internal.SECRET 


class LogCommandRequest(BaseModel):
    discord_id: str
    command: str


@internal.post("/log-command")
async def log_command(
    request: LogCommandRequest,
    x_internal_secret: str = Header(None)
):
    """Internal endpoint for logging command statistics"""
    
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Invalid internal secret")
    
    try:
        logger.info(f"Command executed: {request.command} by user {request.discord_id}")
        
        return {"status": "logged", "message": "Command logged successfully"}
        
    except Exception as e:
        logger.error(f"Failed to log command: {e}")
        raise HTTPException(status_code=500, detail="Failed to log command")
