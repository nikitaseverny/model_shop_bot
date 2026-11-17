"""Order persistence - JSON atomic writes."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from config import Config


@dataclass
class Order:
    """Order data model."""

    id: str
    user_id: int
    username: str | None
    product_id: str
    product_name: str
    color: str
    size: str
    quantity: int
    unit_price_eur: float
    total_price_eur: float
    status: str  # pending, approved, rejected, shipped
    created_at: str  # ISO format
    updated_at: str
    admin_message_id: int | None = None
    shipping_estimate_days: int | None = None
    shipping_estimate_date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Order:
        return cls(**data)


class OrderStore:
    """Thread-safe-ish JSON order store with atomic writes."""

    def __init__(self, data_file: Path) -> None:
        self.data_file = data_file
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.data_file.exists():
            self.data_file.write_text("[]", encoding="utf-8")

    def _load(self) -> list[Order]:
        try:
            content = self.data_file.read_text(encoding="utf-8")
            if not content.strip():
                return []
            data = json.loads(content)
            return [Order.from_dict(item) for item in data]
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, orders: list[Order]) -> None:
        tmp = self.data_file.with_suffix(".tmp")
        data = [order.to_dict() for order in orders]
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.data_file)

    def create(self, order: Order) -> Order:
        orders = self._load()
        orders.append(order)
        self._save(orders)
        return order

    def get_by_id(self, order_id: str) -> Order | None:
        return next((o for o in self._load() if o.id == order_id), None)

    def get_by_user(self, user_id: int) -> list[Order]:
        return [o for o in self._load() if o.user_id == user_id]

    def get_pending(self) -> list[Order]:
        return [o for o in self._load() if o.status == "pending"]

    def update(self, order: Order) -> Order:
        orders = self._load()
        for i, o in enumerate(orders):
            if o.id == order.id:
                order.updated_at = datetime.now(ZoneInfo("UTC")).isoformat()
                orders[i] = order
                self._save(orders)
                return order
        raise ValueError(f"Order not found: {order.id}")

    def update_status(
        self,
        order_id: str,
        status: str,
        shipping_estimate_days: int | None = None,
    ) -> Order | None:
        orders = self._load()
        for i, o in enumerate(orders):
            if o.id == order_id:
                o.status = status
                o.updated_at = datetime.now(ZoneInfo("UTC")).isoformat()
                if shipping_estimate_days is not None:
                    o.shipping_estimate_days = shipping_estimate_days
                self._save(orders)
                return o
        return None


def generate_order_id() -> str:
    """Generate unique order ID."""
    return f"ORD-{int(time.time() * 1000)}"