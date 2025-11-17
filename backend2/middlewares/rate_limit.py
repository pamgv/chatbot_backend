from fastapi import Request, HTTPException
from datetime import datetime, timedelta

RATE_LIMIT_SECONDS = 2  # 1 mensaje cada 2 segundos
user_last_request = {}

async def rate_limit(request: Request):
    body = await request.json()
    username = body.get("username")

    if not username:
        return  # no aplicar si el endpoint no requiere usuario

    now = datetime.utcnow()

    last_time = user_last_request.get(username)

    if last_time and (now - last_time) < timedelta(seconds=RATE_LIMIT_SECONDS):
        raise HTTPException(
            status_code=429,
            detail="You are sending messages too fast. Please wait a moment."
        )

    user_last_request[username] = now
