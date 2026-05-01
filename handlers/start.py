from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from services.wp_service import get_player, create_player
from prompts import THEMES, TEXT_LENGTHS

AWAITING_NAME         = 0
AWAITING_THEME        = 1
AWAITING_CUSTOM_THEME = 2
AWAITING_TEXT_LENGTH  = 3


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id
    player = await get_player(telegram_id)

    if player:
        context.user_data["player"] = player
        await update.message.reply_text(
            f"Bienvenido de vuelta, *{player['name']}*.\nTu aventura continúa...",
            parse_mode="Markdown",
        )
        from handlers.game import start_story
        await start_story(update, context, is_new=False)
        return ConversationHandler.END

    await update.message.reply_text(
        "⚔️ *StoryForge*\n\n"
        "Un mundo te aguarda, viajero.\n\n"
        "¿Cuál es el nombre de tu personaje?",
        parse_mode="Markdown",
    )
    return AWAITING_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()

    if len(name) < 2 or len(name) > 30:
        await update.message.reply_text(
            "El nombre debe tener entre 2 y 30 caracteres. Intenta de nuevo:"
        )
        return AWAITING_NAME

    context.user_data["pending_name"] = name

    keyboard = [
        [InlineKeyboardButton(THEMES[t]["label"], callback_data=f"theme_{t}")]
        for t in THEMES
    ]
    desc_lines = "\n".join(f"{THEMES[t]['label']}: _{THEMES[t]['desc']}_" for t in THEMES)

    await update.message.reply_text(
        f"Perfecto, *{name}*. Ahora elige la temática de tu historia:\n\n{desc_lines}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return AWAITING_THEME


async def receive_theme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    theme = query.data.replace("theme_", "")
    context.user_data["pending_theme"] = theme

    if theme == "custom":
        await query.edit_message_text(
            "✍️ Describe tu temática en una oración.\n"
            "_Ejemplo: 'un cocinero en Tokio que descubre que su restaurante es una fachada de la yakuza'_",
            parse_mode="Markdown",
        )
        return AWAITING_CUSTOM_THEME

    return await _ask_text_length(query)


async def receive_custom_theme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    custom = update.message.text.strip()

    if len(custom) < 5:
        await update.message.reply_text("Escribe al menos una oración describiendo la temática:")
        return AWAITING_CUSTOM_THEME

    context.user_data["pending_custom_theme"] = custom
    return await _ask_text_length(update)


async def receive_text_length(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    text_length  = query.data.replace("length_", "")
    name         = context.user_data["pending_name"]
    theme        = context.user_data["pending_theme"]
    custom_theme = context.user_data.get("pending_custom_theme", "")
    telegram_id  = update.effective_user.id

    player = {
        "telegram_id":     telegram_id,
        "name":            name,
        "theme":           theme,
        "custom_theme":    custom_theme,
        "text_length":     text_length,
        "level":           1,
        "experience":      0,
        "story_summary":   "",
        "current_chapter": "inicio",
        "inventory":       [],
    }

    await create_player(player)
    context.user_data["player"] = player

    theme_label  = THEMES.get(theme, {}).get("label", theme)
    length_label = TEXT_LENGTHS[text_length]["label"]

    await query.edit_message_text(
        f"*{name}* listo.\n\n"
        f"🌍 Temática: {theme_label}\n"
        f"📄 Texto: {length_label}\n\n"
        f"_Que comience la aventura..._",
        parse_mode="Markdown",
    )

    from handlers.game import start_story
    await start_story(update, context, is_new=True)
    return ConversationHandler.END


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _ask_text_length(source):
    keyboard = [[
        InlineKeyboardButton(TEXT_LENGTHS[k]["label"], callback_data=f"length_{k}")
        for k in TEXT_LENGTHS
    ]]
    desc = "\n".join(f"{TEXT_LENGTHS[k]['label']}: {TEXT_LENGTHS[k]['desc']}" for k in TEXT_LENGTHS)
    text = f"¿Cuánto texto querés por escena?\n\n{desc}"

    if hasattr(source, "edit_message_text"):
        await source.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await source.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return AWAITING_TEXT_LENGTH


# ─── ConversationHandler ──────────────────────────────────────────────────────

def get_start_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            AWAITING_NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AWAITING_THEME:        [CallbackQueryHandler(receive_theme,       pattern=r"^theme_")],
            AWAITING_CUSTOM_THEME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_theme)],
            AWAITING_TEXT_LENGTH:  [CallbackQueryHandler(receive_text_length, pattern=r"^length_")],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )
