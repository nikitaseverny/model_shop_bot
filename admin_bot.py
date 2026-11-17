"""Admin bot - receives webhooks and sends approval messages."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiohttp import web
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import Config
from storage import Order, OrderStore, generate_order_id
from admin_notifier import AdminNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

CB_PREFIX = "shop"
CB_ADMIN_APPROVE = f"{CB_PREFIX}:admin:approve"
CB_ADMIN_REJECT = f"{CB_PREFIX}:admin:reject"
CB_ADMIN_SHIP = f"{CB_PREFIX}:admin:ship"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin chat ID."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    await update.message.reply_html(
        f"👋 Admin Bot Active\n\n"
        f"Your Chat ID: <code>{chat_id}</code>\n"
        f"Add this to ADMIN_CHAT_IDS in main bot .env\n\n"
        f"Commands:\n"
        f"• /pending - Show pending orders\n"
        f"• /all - Show all orders"
    )


async def pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show pending orders."""
    store: OrderStore = context.bot_data["store"]
    orders = store.get_pending()

    if not orders:
        await update.message.reply_text("✅ No pending orders.")
        return

    for order in orders:
        text = (
            f"📋 <b>Order {order.id}</b>\n"
            f"👤 User: @{order.username or 'N/A'} ({order.user_id})\n"
            f"📦 {order.product_name}\n"
            f"🎨 {order.color} | 📏 {order.size} | 🔢 ×{order.quantity}\n"
            f"💵 {order.total_price_eur:.2f} EUR\n"
            f"📅 {order.created_at[:16].replace('T', ' ')}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"{CB_ADMIN_APPROVE}:{order.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"{CB_ADMIN_REJECT}:{order.id}"),
            ]
        ])

        await update.message.reply_html(text, reply_markup=keyboard)


async def all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all orders (admin only)."""
    store: OrderStore = context.bot_data["store"]
    orders = store._load()

    if not orders:
        await update.message.reply_text("No orders yet.")
        return

    text = "📋 <b>All Orders</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for order in sorted(orders, key=lambda o: o.created_at, reverse=True)[:20]:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌", "shipped": "📦"}.get(order.status, "❓")
        text += f"{status_emoji} {order.id} - {order.product_name} ({order.status})\n"

    await update.message.reply_html(text)


async def on_admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin clicks approve - show shipping options."""
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[2]
    store: OrderStore = context.bot_data["store"]
    order = store.get_by_id(order_id)

    if not order:
        await query.answer("Order not found", show_alert=True)
        return

    if order.status != "pending":
        await query.answer(f"Order already {order.status}", show_alert=True)
        return

    # Show shipping estimate keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("3 days", callback_data=f"{CB_ADMIN_SHIP}:{order_id}:3"),
            InlineKeyboardButton("5 days", callback_data=f"{CB_ADMIN_SHIP}:{order_id}:5"),
            InlineKeyboardButton("7 days", callback_data=f"{CB_ADMIN_SHIP}:{order_id}:7"),
        ],
        [
            InlineKeyboardButton("10 days", callback_data=f"{CB_ADMIN_SHIP}:{order_id}:10"),
            InlineKeyboardButton("14 days", callback_data=f"{CB_ADMIN_SHIP}:{order_id}:14"),
        ],
        [InlineKeyboardButton("❌ Reject", callback_data=f"{CB_ADMIN_REJECT}:{order_id}")],
    ])

    await query.edit_message_text(
        f"🚚 <b>Set Shipping Estimate for {order_id}</b>\n\n"
        f"📦 {order.product_name}\n"
        f"🎨 {order.color} | 📏 {order.size} | 🔢 ×{order.quantity}\n\n"
        f"Select estimated business days to ship:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def on_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin rejects order."""
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[2]
    store: OrderStore = context.bot_data["store"]
    config: Config = context.bot_data["config"]
    notifier = context.bot_data["notifier"]

    order = store.get_by_id(order_id)
    if not order:
        await query.answer("Order not found", show_alert=True)
        return

    order.status = "rejected"
    order.updated_at = datetime.now(config.timezone).isoformat()
    store.update(order)

    # Notify user via main bot (would need main bot token - simplified here)
    await notifier.notify_order_update(order, "rejected")

    await query.edit_message_text(
        f"❌ <b>Order {order_id} Rejected</b>\n\n"
        f"User has been notified.",
        parse_mode=ParseMode.HTML,
    )


async def on_admin_ship(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin sets shipping estimate."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    order_id = parts[2]
    days = int(parts[3])

    store: OrderStore = context.bot_data["store"]
    config: Config = context.bot_data["config"]
    notifier = context.bot_data["notifier"]

    order = store.get_by_id(order_id)
    if not order:
        await query.answer("Order not found", show_alert=True)
        return

    if order.status != "pending":
        await query.answer(f"Order already {order.status}", show_alert=True)
        return

    # Calculate ship date
    ship_date = datetime.now(config.timezone) + timedelta(days=days)
    ship_date_str = ship_date.strftime("%Y-%m-%d")

    order.status = "approved"
    order.shipping_estimate_days = days
    order.shipping_estimate_date = ship_date_str
    order.updated_at = datetime.now(config.timezone).isoformat()
    store.update(order)

    # Notify user
    await notifier.notify_order_update(order, "approved")

    await query.edit_message_text(
        f"✅ <b>Order {order_id} Approved</b>\n\n"
        f"🚚 Shipping estimate: {days} business days\n"
        f"📦 Estimated ship date: {ship_date_str}\n\n"
        f"User has been notified.",
        parse_mode=ParseMode.HTML,
    )


# ─── Webhook Handler ───

async def webhook_handler(request: web.Request) -> web.Response:
    """Handle incoming webhook from main bot."""
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    logger.info("Webhook received: %s", data.get("type"))

    # Get application from app context
    app: Application = request.app["bot_app"]
    store: OrderStore = app.bot_data["store"]
    config: Config = app.bot_data["config"]
    notifier = app.bot_data["notifier"]

    if data.get("type") == "new_order":
        # Create order object from webhook data
        order = Order(
            id=data["order_id"],
            user_id=data["user_id"],
            username=data.get("username"),
            product_id="",  # Not needed for admin view
            product_name=data["product_name"],
            color=data["color"],
            size=data["size"],
            quantity=data["quantity"],
            unit_price_eur=0,
            total_price_eur=data["total_price_eur"],
            status="pending",
            created_at=data["created_at"],
            updated_at=data["created_at"],
        )

        store.create(order)

        # Send notification to each admin chat
        for chat_id in data.get("chat_ids", []):
            try:
                text = (
                    f"🔔 <b>New Order Received</b>\n\n"
                    f"📋 Order: <code>{order.id}</code>\n"
                    f"👤 User: @{order.username or 'N/A'} ({order.user_id})\n"
                    f"📦 {order.product_name}\n"
                    f"🎨 {order.color} | 📏 {order.size} | 🔢 ×{order.quantity}\n"
                    f"💵 {order.total_price_eur:.2f} EUR\n"
                    f"📅 {order.created_at[:16].replace('T', ' ')}"
                )

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"{CB_ADMIN_APPROVE}:{order.id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"{CB_ADMIN_REJECT}:{order.id}"),
                    ]
                ])

                await app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.warning("Failed to notify admin %s: %s", chat_id, e)

        return web.Response(status=200, text="OK")

    elif data.get("type") == "order_update":
        # Could handle order updates from main bot if needed
        return web.Response(status=200, text="OK")

    return web.Response(status=400, text="Unknown type")


# ─── Application Setup ───

async def create_admin_app(config: Config) -> Application:
    """Create admin bot application."""
    store = OrderStore(config.data_file)
    notifier = AdminNotifier(
        admin_bot_url=config.admin_bot_url,
        admin_chat_ids=config.admin_chat_ids,
    )

    application = (
        Application.builder()
        .token(config.admin_bot_token)
        .post_init(admin_post_init)
        .build()
    )

    application.bot_data["config"] = config
    application.bot_data["store"] = store
    application.bot_data["notifier"] = notifier

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pending", pending_orders))
    application.add_handler(CommandHandler("all", all_orders))
    application.add_handler(CallbackQueryHandler(on_admin_approve, pattern=f"^{CB_ADMIN_APPROVE}:"))
    application.add_handler(CallbackQueryHandler(on_admin_reject, pattern=f"^{CB_ADMIN_REJECT}:"))
    application.add_handler(CallbackQueryHandler(on_admin_ship, pattern=f"^{CB_ADMIN_SHIP}:"))

    return application


async def admin_post_init(application: Application) -> None:
    from telegram import BotCommand

    commands = [
        BotCommand("start", "🔧 Admin panel"),
        BotCommand("pending", "⏳ Pending orders"),
        BotCommand("all", "📋 All orders"),
    ]
    await application.bot.set_my_commands(commands)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def run_admin_bot(config: Config) -> None:
    """Run admin bot with webhook server."""
    if not config.admin_bot_token:
        raise RuntimeError("ADMIN_BOT_TOKEN not set")

    application = await create_admin_app(config)

    # Start polling AND webhook
    await application.initialize()
    await application.updater.start_polling()

    # Start aiohttp webhook server
    web_app = web.Application()
    web_app["bot_app"] = application
    web_app.router.add_post("/notify", webhook_handler)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

    logger.info("Admin bot running - polling + webhook on :8080/notify")

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        await application.updater.stop_polling()
        await application.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    import asyncio

    config = Config.from_env()
    asyncio.run(run_admin_bot(config))