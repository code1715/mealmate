from fastapi import Header, HTTPException, status
import httpx

from app.config import settings


async def require_restaurant_role(authorization: str = Header(...)) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.auth_service_url}/api/auth/validate",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable",
            )
    if resp.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    if resp.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    data = resp.json()
    if data.get("role") != "restaurant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return data
