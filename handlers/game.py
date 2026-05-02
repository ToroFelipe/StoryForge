from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.ollama_service import (
    generate_story, compress_summary,
    get_default_model, get_models_for_ui,
)
from services.db_service import update_player, delete_player
from services.context_service import list_files as list_context_files
from prompts import (
    build_story_prompt, build_intro_prompt,
    build_advance_prompt, build_theme_transition_prompt,
    get_system_prompt, TEXT_LENGTHS, THEMES,
)
from config import AI_PROVIDER

_XP_PER_ACTION       = 10
_XP_PER_LEVEL        = 100
_MAX_SUMMARY_LEN     = 1500
_MAX_RECENT          = 6
_COMPRESS_EVERY      = 5
_BTN_MAX_CHARS       = 55
_CHOICE_EMOJI        = ["①", "②", "③"]


def _truncate(text: str, limit: int = _BTN_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _get_model(player: dict) -> str:
    return player.get("model", get_default_model())


def _get_system(player: dict) -> str:
    return get_system_prompt(
        theme=player.get("theme", "fantasy"),
        text_length=player.get("text_length", "normal"),
        custom_theme=player.get("custom_theme", ""),
        context_key=player.get("context_key", ""),
    )


# ─── Teclado de escena ─────────────────────────────────────────────────────────

async def _send_story(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      narration: str, choices: list):
    keyboard = [
        [InlineKeyboardButton(f"{_CHOICE_EMOJI[i]} {_truncate(c)}", callback_data=f"choice_{i}")]
        for i, c in enumerate(choices[:3])
    ]
    keyboard.append([
        InlineKeyboardButton("⏭️ Avanzar",  callback_data="action_advance"),
        InlineKeyboardButton("📊 Stats",    callback_data="action_stats"),
        InlineKeyboardButton("📖 Recordar", callback_data="action_remember"),
        InlineKeyboardButton("⚙️ Config",   callback_data="action_config"),
    ])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=narration,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── Inicio de historia ────────────────────────────────────────────────────────

async def start_story(update: Update, context: ContextTypes.DEFAULT_TYPE, is_new: bool):
    player = context.user_data["player"]
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    prompt = build_intro_prompt(player) if is_new else build_story_prompt(player, "continúa la historia")
    result = await generate_story(prompt, system=_get_system(player), model=_get_model(player))

    context.user_data["last_choices"] = result["choices"]
    _update_context(player, result["summary"], result["new_npcs"], action=None)
    context.user_data["player"] = player

    await _send_story(update, context, result["narration"], result["choices"])


# ─── Elección del jugador ──────────────────────────────────────────────────────

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player = context.user_data.get("player")
    if not player:
        await query.message.reply_text("❌ Sesión expirada. Usa /start para continuar.")
        return

    idx     = int(query.data.replace("choice_", ""))
    choices = context.user_data.get("last_choices", [])
    if idx >= len(choices):
        return

    action = choices[idx]
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"> {action}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    result = await generate_story(
        build_story_prompt(player, action),
        system=_get_system(player),
        model=_get_model(player),
    )
    context.user_data["last_choices"] = result["choices"]

    # Actualizar NPC registry, resumen y eventos
    _update_context(player, result["summary"], result["new_npcs"], action=action)

    # XP y nivel
    player["experience"] = int(player.get("experience", 0)) + _XP_PER_ACTION
    new_level  = 1 + player["experience"] // _XP_PER_LEVEL
    leveled_up = new_level > int(player.get("level", 1))
    player["level"] = new_level

    # Auto-compresión cada N acciones
    action_count = len(player.get("recent_events", []))
    if action_count > 0 and action_count % _COMPRESS_EVERY == 0:
        old = player.get("story_summary", "")
        if old and len(old) > 400:
            compressed = await compress_summary(old, model=_get_model(player))
            player["story_summary"] = compressed

    context.user_data["player"] = player

    await update_player(player["telegram_id"], {
        "experience":    player["experience"],
        "level":         player["level"],
        "story_summary": player["story_summary"],
    })

    narration = result["narration"]
    if leveled_up:
        narration += f"\n\n🌟 ¡Subiste al nivel {new_level}!"

    await _send_story(update, context, narration, result["choices"])


# ─── Avanzar escena ────────────────────────────────────────────────────────────

async def handle_advance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player = context.user_data.get("player")
    if not player:
        await query.message.reply_text("❌ Sesión expirada. Usa /start para continuar.")
        return

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("⏭️ Saltando a la siguiente escena...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    result = await generate_story(
        build_advance_prompt(player),
        system=_get_system(player),
        model=_get_model(player),
    )
    context.user_data["last_choices"] = result["choices"]
    _update_context(player, result["summary"], result["new_npcs"], action="[avance de escena]")
    context.user_data["player"] = player

    await update_player(player["telegram_id"], {"story_summary": player["story_summary"]})
    await _send_story(update, context, result["narration"], result["choices"])


# ─── Stats ─────────────────────────────────────────────────────────────────────

async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player = context.user_data.get("player")
    if not player:
        await query.message.reply_text("❌ Sesión expirada. Usa /start para continuar.")
        return

    xp           = int(player.get("experience", 0))
    level        = int(player.get("level", 1))
    xp_next      = _XP_PER_LEVEL - (xp % _XP_PER_LEVEL)
    inv          = player.get("inventory", [])
    npc_reg      = player.get("npc_registry", {})
    inv_text     = "\n".join(f"  • {i}" for i in inv) if inv else "  • Vacío"
    theme_label  = THEMES.get(player.get("theme", "fantasy"), {}).get("label", "?")
    length_label = TEXT_LENGTHS.get(player.get("text_length", "normal"), {}).get("label", "?")
    model_label  = get_models_for_ui().get(player.get("model", get_default_model()), player.get("model", "?"))
    ctx_key      = player.get("context_key", "")
    ctx_label    = ctx_key.replace("_", " ").title() if ctx_key else "ninguno"

    npc_text = ""
    if npc_reg:
        npc_text = "\nPersonajes conocidos:\n" + "\n".join(
            f"  • {n}: {d[:50]}" for n, d in list(npc_reg.items())[:5]
        )

    await query.message.reply_text(
        f"📊 {player['name']}\n"
        f"{'─' * 28}\n"
        f"⭐ Nivel:       {level}\n"
        f"✨ XP:          {xp}  ({xp_next} para subir)\n"
        f"🌍 Temática:    {theme_label}\n"
        f"📄 Texto:       {length_label}\n"
        f"🤖 Modelo:      {model_label}\n"
        f"📁 Contexto:    {ctx_label}\n\n"
        f"Inventario:\n{inv_text}"
        f"{npc_text}"
    )


# ─── Recordar ──────────────────────────────────────────────────────────────────

async def handle_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player  = context.user_data.get("player")
    summary = player.get("story_summary", "").strip() if player else ""

    if not summary:
        await query.message.reply_text("Tu aventura acaba de comenzar...")
        return

    await query.message.reply_text(f"📖 Lo que ha ocurrido:\n\n{summary}")


# ─── Config ────────────────────────────────────────────────────────────────────

async def handle_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player         = context.user_data.get("player", {})
    current_length = player.get("text_length", "normal")

    keyboard = [
        # Longitud
        [InlineKeyboardButton(
            f"{'✅ ' if k == current_length else ''}{TEXT_LENGTHS[k]['label']}",
            callback_data=f"setlength_{k}",
        ) for k in TEXT_LENGTHS],
        # Temática
        [InlineKeyboardButton("🌍 Cambiar temática",  callback_data="action_changetheme")],
        # Modelo
        [InlineKeyboardButton("🤖 Cambiar modelo",    callback_data="action_changemodel")],
        # Contexto
        [InlineKeyboardButton("📁 Archivo de contexto", callback_data="action_changecontext")],
    ]
    await query.message.reply_text(
        "⚙️ Configuración:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_set_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_length = query.data.replace("setlength_", "")
    player = context.user_data.get("player")
    if not player:
        return

    player["text_length"] = new_length
    context.user_data["player"] = player
    await update_player(player["telegram_id"], {"text_length": new_length})
    await query.edit_message_text(f"✅ Texto cambiado a {TEXT_LENGTHS[new_length]['label']}.")


# ─── Cambiar modelo ────────────────────────────────────────────────────────────

async def handle_change_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player        = context.user_data.get("player", {})
    current_model = player.get("model", get_default_model())
    models        = get_models_for_ui()
    provider_label = "☁️ Groq (nube)" if AI_PROVIDER == "groq" else "🖥️ Ollama (local)"

    keyboard = [
        [InlineKeyboardButton(
            f"{'✅ ' if k == current_model else ''}{v}",
            callback_data=f"setmodel_{k}",
        )]
        for k, v in models.items()
    ]
    hint = ("💡 Modelos gratuitos en la nube" if AI_PROVIDER == "groq"
            else "💡 Para instalar: ollama pull <nombre>")
    await query.edit_message_text(
        f"🤖 Proveedor: {provider_label}\n{hint}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_model = query.data.replace("setmodel_", "")
    player    = context.user_data.get("player")
    if not player:
        return

    player["model"] = new_model
    context.user_data["player"] = player
    label = AVAILABLE_MODELS.get(new_model, new_model)
    await query.edit_message_text(f"✅ Modelo cambiado a {label}.")


# ─── Cambiar contexto ──────────────────────────────────────────────────────────

async def handle_change_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player      = context.user_data.get("player", {})
    current_ctx = player.get("context_key", "")
    files       = list_context_files()

    if not files:
        await query.edit_message_text(
            "📁 No hay archivos en la carpeta context/.\n\n"
            "Crea archivos .txt en esa carpeta con el lore de tu mundo.\n"
            "Ejemplo: context/pokemon.txt"
        )
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{'✅ ' if f['key'] == current_ctx else ''}📄 {f['label']}",
            callback_data=f"setcontext_{f['key']}",
        )]
        for f in files
    ]
    # Opción para quitar contexto
    keyboard.append([InlineKeyboardButton(
        f"{'✅ ' if not current_ctx else ''}❌ Sin contexto",
        callback_data="setcontext_none",
    )])

    await query.edit_message_text(
        "📁 Elige el archivo de contexto para esta historia:\n"
        "El modelo leerá este archivo como lore del mundo.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_set_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ctx_key = query.data.replace("setcontext_", "")
    player  = context.user_data.get("player")
    if not player:
        return

    if ctx_key == "none":
        player["context_key"] = ""
        label = "desactivado"
    else:
        player["context_key"] = ctx_key
        label = ctx_key.replace("_", " ").title()

    context.user_data["player"] = player
    await query.edit_message_text(f"✅ Contexto: {label}.\nEl narrador usará esta información de ahora en adelante.")


# ─── Cambiar temática ──────────────────────────────────────────────────────────

async def handle_change_theme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    player        = context.user_data.get("player", {})
    current_theme = player.get("theme", "fantasy")

    keyboard = [
        [InlineKeyboardButton(
            f"{'✅ ' if k == current_theme else ''}{THEMES[k]['label']}",
            callback_data=f"settheme_{k}",
        )]
        for k in THEMES
    ]
    await query.edit_message_text(
        "🌍 Elige la nueva temática.\nSe generará una transición narrativa:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_set_theme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_theme = query.data.replace("settheme_", "")
    player    = context.user_data.get("player")
    if not player:
        return

    if new_theme == "custom":
        context.user_data["awaiting_custom_theme_change"] = True
        await query.edit_message_text("✍️ Describe la nueva temática en una oración:")
        return

    await _apply_theme_change(query, context, player, new_theme)


async def handle_custom_theme_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("awaiting_custom_theme_change"):
        return False

    custom = update.message.text.strip()
    player = context.user_data.get("player")
    context.user_data.pop("awaiting_custom_theme_change", None)

    player["theme"]        = "custom"
    player["custom_theme"] = custom
    context.user_data["player"] = player

    await update.message.reply_text(f"🌍 Temática: {custom}\nGenerando transición...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    result = await generate_story(
        build_theme_transition_prompt(player, "custom", custom),
        system=get_system_prompt("custom", player.get("text_length", "normal"), custom,
                                 player.get("context_key", "")),
        model=_get_model(player),
    )
    context.user_data["last_choices"] = result["choices"]
    _update_context(player, result["summary"], result["new_npcs"], action="[cambio de temática]")
    context.user_data["player"] = player

    await _send_story(update, context, result["narration"], result["choices"])
    return True


async def _apply_theme_change(query, context, player: dict, new_theme: str):
    theme_info = THEMES[new_theme]
    player["theme"]        = new_theme
    player["custom_theme"] = ""
    context.user_data["player"] = player

    await query.edit_message_text(f"🌍 Cambiando a {theme_info['label']}...")
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

    result = await generate_story(
        build_theme_transition_prompt(player, new_theme, theme_info["desc"]),
        system=get_system_prompt(new_theme, player.get("text_length", "normal"),
                                 context_key=player.get("context_key", "")),
        model=_get_model(player),
    )
    context.user_data["last_choices"] = result["choices"]
    _update_context(player, result["summary"], result["new_npcs"],
                    action=f"[cambio a {theme_info['label']}]")
    context.user_data["player"] = player

    class _FakeUpdate:
        effective_chat = query.message.chat

    await _send_story(_FakeUpdate(), context, result["narration"], result["choices"])


# ─── Reiniciar ─────────────────────────────────────────────────────────────────

async def cmd_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("✅ Sí, empezar de cero", callback_data="reiniciar_confirm"),
        InlineKeyboardButton("❌ Cancelar",            callback_data="reiniciar_cancel"),
    ]]
    await update.message.reply_text(
        "⚠️ ¿Estás seguro? Se borrará tu personaje y toda tu historia.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_reiniciar_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "reiniciar_cancel":
        await query.edit_message_text("Cancelado. Tu aventura sigue en pie.")
        return

    player = context.user_data.get("player")
    if player:
        await delete_player(player["telegram_id"])

    context.user_data.clear()
    await query.edit_message_text("🗑️ Personaje eliminado.\nUsa /start para crear uno nuevo.")


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _update_context(player: dict, summary_part: str,
                    new_npcs: dict, action: str | None):
    # Resumen comprimible
    if summary_part:
        old      = player.get("story_summary", "") or ""
        combined = f"{old} {summary_part}".strip()
        player["story_summary"] = combined[-_MAX_SUMMARY_LEN:]

    # Eventos recientes
    if action:
        recent = player.get("recent_events", [])
        recent.append(action)
        player["recent_events"] = recent[-_MAX_RECENT:]

    # NPC registry
    if new_npcs:
        reg = player.get("npc_registry", {})
        for name, desc in new_npcs.items():
            if name not in reg:   # no sobreescribir NPCs ya registrados
                reg[name] = desc
        player["npc_registry"] = reg
