"""Main bot handlers for the 3D model shop."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    Config,
    PRODUCTS,
    get_product,
    format_price,
    calculate_shipping_days,
    STATE_CATALOG,
    STATE_PRODUCT,
    STATE_COLOR,
    STATE_SIZE,
    STATE_QUANTITY,
    STATE_CONFIRM,
    UD_PRODUCT_ID,
    UD_COLOR,
    UD_SIZE,
    UD_QUANTITY,
    UD_ORDER_ID,
    CB_CATALOG,
    CB_PRODUCT,
    CB_COLOR,
    CB_SIZE,
    CB_QUANTITY,
    CB_CONFIRM,
    CB_CANCEL,
    CB_PREFIX,
)
from keyboards import (
    catalog_keyboard,
    product_keyboard,
    color_keyboard,
    size_keyboard,
    quantity_keyboard,
    confirm_keyboard,
    user_order_keyboard,
)
from storage import Order, OrderStore, generate_order_id
from admin_notifier import AdminNotifier

logger = logging.getLogger(__name__)


# ─── Helpers ───

def _now_iso(config: Config) -> str:
    return datetime.now(config.timezone).isoformat()


def _format_order_summary(order: Order, config: Config) -> str:
    lines = [
        f"🧾 <b>Order Summary</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"📦 Product: {order.product_name}",
        f"🎨 Color: {order.color}",
        f"📏 Size: {order.size}",
        f"🔢 Quantity: {order.quantity}",
        f"💰 Unit Price: {format_price(order.unit_price_eur)}",
        f"💵 <b>Total: {format_price(order.total_price_eur)}</b>",
        f"",
        f"📅 Created: {order.created_at[:16].replace('T', ' ')}",
    ]
    if order.shipping_estimate_days:
        lines.append(f"🚚 Est. Shipping: {order.shipping_estimate_days} business days")
    if order.shipping_estimate_date:
        lines.append(f"📦 Est. Ship Date: {order.shipping_estimate_date}")
    return "\n".join(lines)


# ─── Command Handlers ───

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point - show catalog."""
    config: Config = context.bot_data["config"]
    store: OrderStore = context.bot_data["store"]
    notifier: AdminNotifier = context.bot_data["notifier"]

    # Clear any previous conversation state
    context.user_data.clear()

    text = (
        "🏪 <b>Welcome to 3D Model Shop!</b>\n\n"
        "Browse our collection of high-quality 3D printable models.\n"
        "Select a product to customize color, size, and quantity."
    )

    if update.message:
        await update.message.reply_html(text, reply_markup=catalog_keyboard())
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=catalog_keyboard())

    return STATE_CATALOG


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help."""
    text = (
        "🤖 <b>3D Model Shop Bot - Help</b>\n\n"
        "<b>Commands:</b>\n"
        "• /start - Browse catalog\n"
        "• /myorders - View your orders\n"
        "• /help - Show this help\n\n"
        "<b>How to order:</b>\n"
        "1. Browse catalog and tap a product\n"
        "2. Choose color 🎨\n"
        "3. Choose size 📏\n"
        "4. Set quantity 🔢\n"
        "5. Confirm order ✅\n\n"
        "<b>After confirmation:</b>\n"
        "• Admin receives your order\n"
        "• Admin approves and sets shipping timeline\n"
        "• You get notified with estimated ship date\n\n"
        "All models are digital files for 3D printing."
    )
    await update.message.reply_html(text)


async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's orders."""
    config: Config = context.bot_data["config"]
    store: OrderStore = context.bot_data["store"]

    user_id = update.effective_user.id
    orders = store.get_by_user(user_id)

    if not orders:
        await update.message.reply_html("📭 You have no orders yet. Use /start to browse!")
        return

    text = "📋 <b>Your Orders</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for order in sorted(orders, key=lambda o: o.created_at, reverse=True):
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "shipped": "📦",
        }.get(order.status, "❓")

        text += (
            f"{status_emoji} <b>{order.id}</b> - {order.product_name}\n"
            f"   {order.color} / {order.size} ×{order.quantity}\n"
            f"   {format_price(order.total_price_eur)} • {order.status.capitalize()}\n\n"
        )

    await update.message.reply_html(text)


# ─── Callback Handlers ───

async def on_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show catalog."""
    query = update.callback_query
    await query.answer()

    text = "🛍 <b>Catalog</b>\n\nTap a product to view details and customize:"
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=catalog_keyboard())
    return STATE_CATALOG


async def on_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show product detail."""
    query = update.callback_query
    await query.answer()

    # Parse: shop:product:<product_id>
    _, _, product_id = query.data.split(":", 2)
    product = get_product(product_id)

    if not product:
        await query.answer("Product not found", show_alert=True)
        return STATE_CATALOG

    # Store product_id in user_data
    context.user_data[UD_PRODUCT_ID] = product_id
    # Initialize selections
    context.user_data[UD_COLOR] = product["colors"][0]
    context.user_data[UD_SIZE] = product["sizes"][0]
    context.user_data[UD_QUANTITY] = 1

    text = (
        f"📦 <b>{product['name']}</b>\n"
        f"💰 Price: {format_price(product['price_eur'])}\n\n"
        f"{product['description']}\n\n"
        f"🎨 Colors: {', '.join(product['colors'])}\n"
        f"📏 Sizes: {', '.join(product['sizes'])}\n\n"
        f"<b>Current selection:</b>\n"
        f"🎨 Color: {context.user_data[UD_COLOR]}\n"
        f"📏 Size: {context.user_data[UD_SIZE]}\n"
        f"🔢 Quantity: {context.user_data[UD_QUANTITY]}"
    )

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=product_keyboard(product_id))
    return STATE_PRODUCT


async def on_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle color selection."""
    query = update.callback_query
    await query.answer()

    # Parse: shop:color:<product_id>:<color>
    parts = query.data.split(":", 3)
    product_id = parts[2]
    color = parts[3] if len(parts) > 3 else None

    product = get_product(product_id)
    if not product:
        await query.answer("Product not found", show_alert=True)
        return STATE_PRODUCT

    if color:
        context.user_data[UD_COLOR] = color

    text = (
        f"🎨 <b>Choose Color for {product['name']}</b>\n\n"
        f"Current: <b>{context.user_data[UD_COLOR]}</b>\n\n"
        f"Tap a color to select:"
    )

    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=color_keyboard(product_id, context.user_data[UD_COLOR])
    )
    return STATE_COLOR


async def on_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle size selection."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 3)
    product_id = parts[2]
    size = parts[3] if len(parts) > 3 else None

    product = get_product(product_id)
    if not product:
        await query.answer("Product not found", show_alert=True)
        return STATE_PRODUCT

    if size:
        context.user_data[UD_SIZE] = size

    text = (
        f"📏 <b>Choose Size for {product['name']}</b>\n\n"
        f"Current: <b>{context.user_data[UD_SIZE]}</b>\n\n"
        f"Tap a size to select:"
    )

    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=size_keyboard(product_id, context.user_data[UD_SIZE])
    )
    return STATE_SIZE


async def on_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quantity selection."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    product_id = parts[2]
    action = parts[3]

    product = get_product(product_id)
    if not product:
        await query.answer("Product not found", show_alert=True)
        return STATE_PRODUCT

    current = context.user_data.get(UD_QUANTITY, 1)

    if action == "increase":
        current = min(current + 1, 99)
    elif action == "decrease":
        current = max(current - 1, 1)
    elif action == "set":
        current = int(parts[4])
    elif action == "current":
        pass  # Just refresh

    context.user_data[UD_QUANTITY] = current

    text = (
        f"🔢 <b>Set Quantity for {product['name']}</b>\n\n"
        f"Current: <b>{current}</b>\n\n"
        f"Use buttons to adjust:"
    )

    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=quantity_keyboard(product_id, current)
    )
    return STATE_QUANTITY


async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show order confirmation."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    product_id = parts[2]
    action = parts[3] if len(parts) > 3 else None

    product = get_product(product_id)
    if not product:
        await query.answer("Product not found", show_alert=True)
        return STATE_PRODUCT

    if action == "yes":
        # Create order
        config: Config = context.bot_data["config"]
        store: OrderStore = context.bot_data["store"]
        notifier: AdminNotifier = context.bot_data["notifier"]

        user = update.effective_user
        order_id = generate_order_id()

        order = Order(
            id=order_id,
            user_id=user.id,
            username=user.username,
            product_id=product_id,
            product_name=product["name"],
            color=context.user_data[UD_COLOR],
            size=context.user_data[UD_SIZE],
            quantity=context.user_data[UD_QUANTITY],
            unit_price_eur=product["price_eur"],
            total_price_eur=round(Decimal(str(product["price_eur"])) * context.user_data[UD_QUANTITY], 2),
            status="pending",
            created_at=_now_iso(config),
            updated_at=_now_iso(config),
        )

        store.create(order)

        # Notify admin
        await notifier.notify_new_order(order)

        text = (
            f"✅ <b>Order Placed!</b>\n\n"
            f"📋 Order ID: <code>{order_id}</code>\n\n"
            f"{_format_order_summary(order, config)}\n\n"
            f"⏳ <b>Waiting for admin confirmation...</b>\n"
            f"You'll receive a notification when your order is approved with shipping timeline."
        )

        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=user_order_keyboard(order_id)
        )

        # Store order_id for status checks
        context.user_data[UD_ORDER_ID] = order_id

        return STATE_CONFIRM

    # action == "no" or just showing confirmation
    text = (
        f"✅ <b>Confirm Your Order</b>\n\n"
        f"📦 Product: {product['name']}\n"
        f"🎨 Color: {context.user_data[UD_COLOR]}\n"
        f"📏 Size: {context.user_data[UD_SIZE]}\n"
        f"🔢 Quantity: {context.user_data[UD_QUANTITY]}\n"
        f"💰 Unit: {format_price(product['price_eur'])}\n"
        f"💵 <b>Total: {format_price(round(Decimal(str(product['price_eur'])) * context.user_data[UD_QUANTITY], 2))}</b>\n\n"
        f"Confirm to send to admin for approval:"
    )

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard(product_id))
    return STATE_CONFIRM


async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel current order flow."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ Order cancelled. Use /start to browse again.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 Browse Catalog", callback_data=CB_CATALOG)]
        ]),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def on_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to previous step."""
    query = update.callback_query
    await query.answer()

    # Determine where to go back based on current state
    # For simplicity, go back to product view
    product_id = context.user_data.get(UD_PRODUCT_ID)
    if product_id:
        return await on_product(update, context)
    return await on_catalog(update, context)


async def on_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check order status."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    order_id = parts[2]

    store: OrderStore = context.bot_data["store"]
    config: Config = context.bot_data["config"]

    order = store.get_by_id(order_id)
    if not order:
        await query.answer("Order not found", show_alert=True)
        return

    if order.user_id != update.effective_user.id:
        await query.answer("Not your order", show_alert=True)
        return

    text = _format_order_summary(order, config)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=user_order_keyboard(order_id))


# ─── Admin Callbacks (handled by admin bot, but included for reference) ───

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin approves order - show shipping estimate options."""
    query = update.callback_query
    await query.answer()

    # This would be handled by admin bot
    pass


async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin rejects order."""
    pass


async def admin_set_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin sets shipping estimate."""
    pass


# ─── Application Setup ───

def create_application(config: Config) -> Application:
    """Create and configure the bot application."""
    store = OrderStore(config.data_file)
    notifier = AdminNotifier(
        admin_bot_url=config.admin_bot_url,
        admin_chat_ids=config.admin_chat_ids,
    )

    application = (
        Application.builder()
        .token(config.bot_token)
        .post_init(post_init)
        .build()
    )

    # Store shared objects in bot_data
    application.bot_data["config"] = config
    application.bot_data["store"] = store
    application.bot_data["notifier"] = notifier

    # Conversation handler for ordering flow
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(on_catalog, pattern=f"^{CB_CATALOG}$"),
        ],
        states={
            STATE_CATALOG: [
                CallbackQueryHandler(on_product, pattern=f"^{CB_PRODUCT}:"),
            ],
            STATE_PRODUCT: [
                CallbackQueryHandler(on_color, pattern=f"^{CB_COLOR}:"),
                CallbackQueryHandler(on_size, pattern=f"^{CB_SIZE}:"),
                CallbackQueryHandler(on_quantity, pattern=f"^{CB_QUANTITY}:"),
                CallbackQueryHandler(on_confirm, pattern=f"^{CB_CONFIRM}:"),
                CallbackQueryHandler(on_catalog, pattern=f"^{CB_CATALOG}$"),
            ],
            STATE_COLOR: [
                CallbackQueryHandler(on_color, pattern=f"^{CB_COLOR}:"),
                CallbackQueryHandler(on_product, pattern=f"^{CB_PRODUCT}:"),
            ],
            STATE_SIZE: [
                CallbackQueryHandler(on_size, pattern=f"^{CB_SIZE}:"),
                CallbackQueryHandler(on_product, pattern=f"^{CB_PRODUCT}:"),
            ],
            STATE_QUANTITY: [
                CallbackQueryHandler(on_quantity, pattern=f"^{CB_QUANTITY}:"),
                CallbackQueryHandler(on_product, pattern=f"^{CB_PRODUCT}:"),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(on_confirm, pattern=f"^{CB_CONFIRM}:"),
                CallbackQueryHandler(on_cancel, pattern=f"^{CB_CANCEL}:"),
                CallbackQueryHandler(on_product, pattern=f"^{CB_PRODUCT}:"),
                CallbackQueryHandler(on_status, pattern=f"^{CB_PREFIX}:status:"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(on_catalog, pattern=f"^{CB_CATALOG}$"),
        ],
        per_user=True,
        per_chat=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myorders", myorders))

    return application


async def post_init(application: Application) -> None:
    """Set up command menu (side menu ☰)."""
    from telegram import BotCommand

    commands = [
        BotCommand("start", "🛍 Browse catalog"),
        BotCommand("myorders", "📋 My orders"),
        BotCommand("help", "❓ Help"),
    ]
    await application.bot.set_my_commands(commands)

    # Suppress token logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)