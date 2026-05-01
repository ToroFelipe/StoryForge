import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters, ContextTypes,
)
from config import TELEGRAM_TOKEN
from handlers.start import get_start_handler
from handlers.game import (
    handle_choice, handle_advance,
    handle_stats, handle_remember,
    handle_config, handle_set_length,
    handle_change_theme, handle_set_theme,
    handle_change_model, handle_set_model,
    handle_change_context, handle_set_context,
    handle_custom_theme_input,
    cmd_reiniciar, handle_reiniciar_confirm,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def _route_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_custom_theme_input(update, context)


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Falta TELEGRAM_TOKEN en el archivo .env")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(get_start_handler())
    app.add_handler(CommandHandler("reiniciar", cmd_reiniciar))

    # Juego
    app.add_handler(CallbackQueryHandler(handle_choice,            pattern=r"^choice_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_advance,           pattern=r"^action_advance$"))
    app.add_handler(CallbackQueryHandler(handle_stats,             pattern=r"^action_stats$"))
    app.add_handler(CallbackQueryHandler(handle_remember,          pattern=r"^action_remember$"))
    # Config
    app.add_handler(CallbackQueryHandler(handle_config,            pattern=r"^action_config$"))
    app.add_handler(CallbackQueryHandler(handle_set_length,        pattern=r"^setlength_"))
    app.add_handler(CallbackQueryHandler(handle_change_theme,      pattern=r"^action_changetheme$"))
    app.add_handler(CallbackQueryHandler(handle_set_theme,         pattern=r"^settheme_"))
    app.add_handler(CallbackQueryHandler(handle_change_model,      pattern=r"^action_changemodel$"))
    app.add_handler(CallbackQueryHandler(handle_set_model,         pattern=r"^setmodel_"))
    app.add_handler(CallbackQueryHandler(handle_change_context,    pattern=r"^action_changecontext$"))
    app.add_handler(CallbackQueryHandler(handle_set_context,       pattern=r"^setcontext_"))
    # Reiniciar
    app.add_handler(CallbackQueryHandler(handle_reiniciar_confirm, pattern=r"^reiniciar_"))
    # Texto libre mid-game
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _route_text))

    print("🗡️  StoryForge Bot iniciado. Esperando jugadores...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
