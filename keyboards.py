"""Inline keyboards for the shop bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    CB_CANCEL,
    CB_CATALOG,
    CB_COLOR,
    CB_CONFIRM,
    CB_PREFIX,
    CB_PRODUCT,
    CB_QUANTITY,
    CB_SIZE,
    PRODUCTS,
    get_product,
)

if TYPE_CHECKING:
    from config import Config


def catalog_keyboard() -> InlineKeyboardMarkup:
    """Main catalog keyboard with all products."""
    buttons = [
        [InlineKeyboardButton(p["name"], callback_data=f"{CB_PRODUCT}:{p['id']}")]
        for p in PRODUCTS
    ]
    return InlineKeyboardMarkup(buttons)


def product_keyboard(product_id: str) -> InlineKeyboardMarkup:
    """Keyboard for product detail view."""
    product = get_product(product_id)
    if not product:
        return InlineKeyboardMarkup([[]])

    buttons = [
        [InlineKeyboardButton("🎨 Choose Color", callback_data=f"{CB_COLOR}:{product_id}")],
        [InlineKeyboardButton("📏 Choose Size", callback_data=f"{CB_SIZE}:{product_id}")],
        [InlineKeyboardButton("🔢 Set Quantity", callback_data=f"{CB_QUANTITY}:{product_id}")],
        [InlineKeyboardButton("✅ Add to Cart", callback_data=f"{CB_CONFIRM}:{product_id}")],
        [InlineKeyboardButton("⬅️ Back to Catalog", callback_data=CB_CATALOG)],
    ]
    return InlineKeyboardMarkup(buttons)


def color_keyboard(product_id: str, selected: str | None = None) -> InlineKeyboardMarkup:
    """Color selection keyboard."""
    product = get_product(product_id)
    if not product:
        return InlineKeyboardMarkup([[]])

    buttons = []
    row = []
    for color in product["colors"]:
        label = f"✅ {color}" if color == selected else color
        row.append(InlineKeyboardButton(label, callback_data=f"{CB_COLOR}:{product_id}:{color}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_PRODUCT}:{product_id}")])
    return InlineKeyboardMarkup(buttons)


def size_keyboard(product_id: str, selected: str | None = None) -> InlineKeyboardMarkup:
    """Size selection keyboard."""
    product = get_product(product_id)
    if not product:
        return InlineKeyboardMarkup([[]])

    buttons = []
    row = []
    for size in product["sizes"]:
        label = f"✅ {size}" if size == selected else size
        row.append(InlineKeyboardButton(label, callback_data=f"{CB_SIZE}:{product_id}:{size}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_PRODUCT}:{product_id}")])
    return InlineKeyboardMarkup(buttons)


def quantity_keyboard(product_id: str, current: int = 1) -> InlineKeyboardMarkup:
    """Quantity selection keyboard."""
    buttons = [
        [
            InlineKeyboardButton("➖", callback_data=f"{CB_QUANTITY}:{product_id}:decrease"),
            InlineKeyboardButton(f"{current}", callback_data=f"{CB_QUANTITY}:{product_id}:current"),
            InlineKeyboardButton("➕", callback_data=f"{CB_QUANTITY}:{product_id}:increase"),
        ],
        [
            InlineKeyboardButton("1", callback_data=f"{CB_QUANTITY}:{product_id}:set:1"),
            InlineKeyboardButton("2", callback_data=f"{CB_QUANTITY}:{product_id}:set:2"),
            InlineKeyboardButton("3", callback_data=f"{CB_QUANTITY}:{product_id}:set:3"),
            InlineKeyboardButton("5", callback_data=f"{CB_QUANTITY}:{product_id}:set:5"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_PRODUCT}:{product_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(product_id: str) -> InlineKeyboardMarkup:
    """Order confirmation keyboard."""
    buttons = [
        [
            InlineKeyboardButton("✅ Confirm Order", callback_data=f"{CB_CONFIRM}:{product_id}:yes"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CB_CANCEL}:{product_id}"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_PRODUCT}:{product_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Admin approval keyboard."""
    buttons = [
        [
            InlineKeyboardButton("✅ Approve & Set Shipping", callback_data=f"{CB_PREFIX}:admin:approve:{order_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"{CB_PREFIX}:admin:reject:{order_id}"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def shipping_estimate_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Keyboard for admin to set shipping estimate."""
    buttons = [
        [
            InlineKeyboardButton("3 days", callback_data=f"{CB_PREFIX}:admin:ship:{order_id}:3"),
            InlineKeyboardButton("5 days", callback_data=f"{CB_PREFIX}:admin:ship:{order_id}:5"),
            InlineKeyboardButton("7 days", callback_data=f"{CB_PREFIX}:admin:ship:{order_id}:7"),
        ],
        [
            InlineKeyboardButton("10 days", callback_data=f"{CB_PREFIX}:admin:ship:{order_id}:10"),
            InlineKeyboardButton("14 days", callback_data=f"{CB_PREFIX}:admin:ship:{order_id}:14"),
            InlineKeyboardButton("Custom...", callback_data=f"{CB_PREFIX}:admin:ship:{order_id}:custom"),
        ],
        [InlineKeyboardButton("❌ Reject Order", callback_data=f"{CB_PREFIX}:admin:reject:{order_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def user_order_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Keyboard for user to view their order status."""
    buttons = [
        [InlineKeyboardButton("📦 Check Status", callback_data=f"{CB_PREFIX}:status:{order_id}")],
        [InlineKeyboardButton("🛍 Continue Shopping", callback_data=CB_CATALOG)],
    ]
    return InlineKeyboardMarkup(buttons)