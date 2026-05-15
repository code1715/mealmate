"""Best-effort HTTP client for the Routing Service.

Courier assignment is non-critical: any error is logged and None is returned
so the caller can proceed without a courier assignment.
"""

import logging
import uuid

import httpx

logger = logging.getLogger(__name__)


class RoutingClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def assign_courier(
        self, order_id: uuid.UUID, restaurant_id: uuid.UUID
    ) -> uuid.UUID | None:
        """Call POST /api/routing/match and return the assigned courier_id, or None."""
        url = f"{self._base_url}/api/routing/match"
        payload = {
            "order_id": str(order_id),
            "restaurant_id": str(restaurant_id),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return uuid.UUID(resp.json()["courier_id"])
            if resp.status_code == 404:
                logger.info(
                    "No couriers available for order %s (restaurant %s)",
                    order_id,
                    restaurant_id,
                )
                return None
            logger.warning(
                "Routing service returned unexpected status %s for order %s",
                resp.status_code,
                order_id,
            )
            return None
        except Exception as exc:
            logger.error(
                "Routing service unreachable for order %s: %s", order_id, exc
            )
            return None
