"""Admin notification via separate admin bot (webhook)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from config import Config
from storage import Order

logger = logging.getLogger(__name__)


@dataclass
class AdminNotifier:
    """Fire-and-forget admin notifications."""

    admin_bot_url: str | None
    admin_chat_ids: list[int]
    timeout: float = 5.0

    async def notify_new_order(self, order: Order) -> bool:
        """Send new order notification to admin bot."""
        if not self.admin_bot_url:
            logger.warning("ADMIN_BOT_URL not configured, skipping admin notification")
            return False

        payload = {
            "type": "new_order",
            "order_id": order.id,
            "user_id": order.user_id,
            "username": order.username,
            "product_name": order.product_name,
            "color": order.color,
            "size": order.size,
            "quantity": order.quantity,
            "total_price_eur": order.total_price_eur,
            "created_at": order.created_at,
            "chat_ids": self.admin_chat_ids,
        }

        return await self._post(payload)

    async def notify_order_update(self, order: Order, admin_action: str) -> bool:
        """Notify admin bot of order status change."""
        if not self.admin_bot_url:
            return False

        payload = {
            "type": "order_update",
            "order_id": order.id,
            "status": order.status,
            "admin_action": admin_action,
            "shipping_estimate_days": order.shipping_estimate_days,
            "chat_ids": self.admin_chat_ids,
        }

        return await self._post(payload)

    async def _post(self, payload: dict) -> bool:
        """Fire-and-forget POST to admin bot."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.admin_bot_url, json=payload)
                response.raise_for_status()
                logger.info("Admin notification sent: %s", payload.get("type"))
                return True
        except httpx.TimeoutException:
            logger.warning("Admin notification timeout: %s", payload.get("type"))
        except httpx.HTTPStatusError as e:
            logger.warning("Admin notification HTTP error: %s - %s", e.response.status_code, payload.get("type"))
        except Exception as e:
            logger.warning("Admin notification failed: %s - %s", type(e).__name__, e)
        return False