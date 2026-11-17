"""3D Model Shop Telegram Bot - Configuration and constants."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Bot configuration loaded from environment."""

    bot_token: str
    admin_bot_token: str | None
    admin_chat_ids: list[int]
    admin_bot_url: str | None
    timezone: ZoneInfo
    data_file: Path

    # Shipping config
    shipping_base_days: int
    shipping_per_color_days: int
    shipping_per_size_days: int

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment variables."""
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise RuntimeError("BOT_TOKEN not set in environment")

        admin_chat_ids_raw = os.getenv("ADMIN_CHAT_IDS", "")
        admin_chat_ids = [
            int(x.strip()) for x in admin_chat_ids_raw.split(",") if x.strip().isdigit()
        ]

        tz_name = os.getenv("TIMEZONE", "Europe/Riga")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Europe/Riga")

        data_file = Path(os.getenv("DATA_FILE", "orders.json"))

        return cls(
            bot_token=bot_token,
            admin_bot_token=os.getenv("ADMIN_BOT_TOKEN"),
            admin_chat_ids=admin_chat_ids,
            admin_bot_url=os.getenv("ADMIN_BOT_URL"),
            timezone=tz,
            data_file=data_file,
            shipping_base_days=int(os.getenv("SHIPPING_BASE_DAYS", "3")),
            shipping_per_color_days=int(os.getenv("SHIPPING_PER_COLOR_DAYS", "1")),
            shipping_per_size_days=int(os.getenv("SHIPPING_PER_SIZE_DAYS", "1")),
        )


# Product catalog - in production, load from JSON file or database
PRODUCTS: list[dict] = [
    {
        "id": "dragon",
        "name": "🐉 Dragon Figurine",
        "description": "Highly detailed articulated dragon model. Perfect for display or gaming.",
        "price_eur": 24.99,
        "colors": ["Red", "Green", "Blue", "Gold", "Silver"],
        "sizes": ["Small (10cm)", "Medium (15cm)", "Large (20cm)"],
        "photo_url": "https://example.com/dragon.jpg",  # Replace with actual photo URLs
    },
    {
        "id": "castle",
        "name": "🏰 Medieval Castle",
        "description": "Modular castle with towers, walls, and gate. Print in parts and assemble.",
        "price_eur": 39.99,
        "colors": ["Gray", "Sand", "Dark Green", "White"],
        "sizes": ["Standard", "Large (+50%)"],
        "photo_url": "https://example.com/castle.jpg",
    },
    {
        "id": "gear_keychain",
        "name": "⚙️ Mechanical Gear Keychain",
        "description": "Functional planetary gear system. Great fidget toy and keychain.",
        "price_eur": 8.99,
        "colors": ["Black", "White", "Red", "Blue", "Orange", "Glow-in-dark"],
        "sizes": ["Standard"],
        "photo_url": "https://example.com/gear_keychain.jpg",
    },
    {
        "id": "vase",
        "name": "🏺 Voronoi Vase",
        "description": "Algorithmic voronoi pattern vase. Water-tight when printed with 3+ perimeters.",
        "price_eur": 18.50,
        "colors": ["White", "Terracotta", "Black", "Mint", "Lavender"],
        "sizes": ["Small (12cm)", "Medium (18cm)", "Large (25cm)"],
        "photo_url": "https://example.com/vase.jpg",
    },
    {
        "id": "phone_stand",
        "name": "📱 Adjustable Phone Stand",
        "description": "Multi-angle adjustable stand with cable management. Fits all phones.",
        "price_eur": 12.99,
        "colors": ["Black", "White", "Gray", "Blue", "Pink"],
        "sizes": ["Universal"],
        "photo_url": "https://example.com/phone_stand.jpg",
    },
    {
        "id": "chess_set",
        "name": "♟️ Minimalist Chess Set",
        "description": "Modern geometric chess pieces. Weighted bases available as separate print.",
        "price_eur": 34.99,
        "colors": ["Black & White", "Dark & Light Wood", "Gold & Silver", "Red & Blue"],
        "sizes": ["Standard (King 9cm)", "Large (King 12cm)"],
        "photo_url": "https://example.com/chess_set.jpg",
    },
]


def get_product(product_id: str) -> dict | None:
    """Get product by ID."""
    return next((p for p in PRODUCTS if p["id"] == product_id), None)


def format_price(price_eur: float) -> str:
    """Format price in EUR."""
    return f"€{price_eur:.2f}"


def calculate_shipping_days(
    config: Config,
    color: str,
    size: str,
) -> int:
    """Calculate estimated shipping days based on customization."""
    days = config.shipping_base_days
    if color not in ("Standard", "Universal", "Black & White", "Default"):
        days += config.shipping_per_color_days
    if size not in ("Standard", "Universal", "Default"):
        days += config.shipping_per_size_days
    return days


# Conversation states
(
    STATE_CATALOG,
    STATE_PRODUCT,
    STATE_COLOR,
    STATE_SIZE,
    STATE_QUANTITY,
    STATE_CONFIRM,
    STATE_ADMIN_CONFIRM,
) = range(7)


# Callback data prefixes
CB_PREFIX = "shop"
CB_CATALOG = f"{CB_PREFIX}:catalog"
CB_PRODUCT = f"{CB_PREFIX}:product"
CB_COLOR = f"{CB_PREFIX}:color"
CB_SIZE = f"{CB_PREFIX}:size"
CB_QUANTITY = f"{CB_PREFIX}:qty"
CB_CONFIRM = f"{CB_PREFIX}:confirm"
CB_CANCEL = f"{CB_PREFIX}:cancel"
CB_BACK = f"{CB_PREFIX}:back"
CB_ADMIN_APPROVE = f"{CB_PREFIX}:admin:approve"
CB_ADMIN_REJECT = f"{CB_PREFIX}:admin:reject"

# User data keys
UD_PRODUCT_ID = "product_id"
UD_COLOR = "color"
UD_SIZE = "size"
UD_QUANTITY = "quantity"
UD_ORDER_ID = "order_id"