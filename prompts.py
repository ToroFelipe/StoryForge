from services.context_service import load as load_context

THEMES = {
    "fantasy":   {"label": "⚔️ Fantasía oscura",    "desc": "Mundo medieval, magia y peligro"},
    "scifi":     {"label": "🚀 Ciencia ficción",      "desc": "Naves, robots y galaxias lejanas"},
    "student":   {"label": "🎓 Vida universitaria",   "desc": "Campus, exámenes y decisiones"},
    "daily":     {"label": "🌆 Vida cotidiana",        "desc": "Un día común lleno de elecciones"},
    "detective": {"label": "🔍 Detective noir",        "desc": "Crímenes, sombras y secretos"},
    "custom":    {"label": "✍️ Escribir mi temática", "desc": "Define tu propio mundo"},
}

TEXT_LENGTHS = {
    "short":  {"label": "📄 Corto",  "desc": "2-3 oraciones por escena"},
    "normal": {"label": "📖 Normal", "desc": "2-3 párrafos por escena"},
    "long":   {"label": "📚 Largo",  "desc": "4-5 párrafos detallados"},
}

_LENGTH_RULE = {
    "short":  "La NARRACIÓN debe tener exactamente 2 o 3 oraciones. Sé muy conciso.",
    "normal": "La NARRACIÓN debe tener 2 o 3 párrafos.",
    "long":   "La NARRACIÓN debe tener 4 o 5 párrafos ricos en detalles sensoriales.",
}

_FORMAT_RULES = """
FORMATO DE RESPUESTA — obligatorio, sin excepciones:
Responde ÚNICAMENTE con este bloque exacto (sin texto antes ni después):

NARRACIÓN:
[escena según longitud indicada]

OPCIONES:
1. [acción concreta]
2. [acción concreta alternativa]
3. [tercera acción posible]

PERSONAJES:
- [Nombre]: [descripción en 1 línea] (SOLO si aparece por primera vez. Si no hay personajes nuevos, escribe "ninguno")

RESUMEN:
[una sola oración en pasado resumiendo lo que ocurrió]

Reglas narrativas:
- Opciones variadas: una directa/combate, una social/diplomática, una de exploración/sigilo.
- COHERENCIA: si un personaje fue descrito antes, mantén exactamente esa descripción (edad, apariencia, nombre).
- NUNCA repitas situaciones, lugares o diálogos ya narrados en el historial.
- Cada escena avanza la trama: algo nuevo se revela o el estado del mundo cambia.
- Nunca rompas el personaje ni menciones que eres una IA."""

_THEME_PROMPTS = {
    "fantasy": (
        "Eres el narrador de StoryForge, una aventura de fantasía oscura y medieval. "
        "El mundo es brutal, lleno de magia antigua, monstruos y facciones en guerra. "
        "El tono es oscuro, tenso y épico. Los NPCs tienen agendas propias."
    ),
    "scifi": (
        "Eres el narrador de StoryForge, una aventura de ciencia ficción espacial. "
        "El escenario es el año 2387: corporaciones, planetas colonizados, IA rebeldes y guerras estelares. "
        "El tono es tenso y tecnológico, con dilemas morales."
    ),
    "student": (
        "Eres el narrador de StoryForge, una historia de vida universitaria realista. "
        "El mundo es el campus, los departamentos, las fiestas y las relaciones. "
        "Las decisiones tienen consecuencias sociales y académicas."
    ),
    "daily": (
        "Eres el narrador de StoryForge, una historia de vida cotidiana. "
        "El escenario es una ciudad moderna. Cada decisión lleva a caminos muy distintos. "
        "El tono es realista y reflexivo."
    ),
    "detective": (
        "Eres el narrador de StoryForge, un thriller noir de detectives. "
        "Ciudad oscura, años 50. Crímenes sin resolver, testigos que mienten. "
        "El tono es seco, tenso y cinematográfico."
    ),
}

_RECENT_WINDOW = 4


def get_system_prompt(theme: str, text_length: str,
                      custom_theme: str = "", context_key: str = "") -> str:
    # Descripción del mundo
    if theme == "custom" and custom_theme:
        world_desc = (
            f"Eres el narrador de StoryForge. El mundo es: {custom_theme}. "
            f"Mantén coherencia absoluta con esa temática."
        )
    else:
        world_desc = _THEME_PROMPTS.get(theme, _THEME_PROMPTS["fantasy"])

    # Contexto externo (archivo .txt)
    ctx_section = ""
    if context_key:
        ctx = load_context(context_key)
        if ctx:
            ctx_section = f"\n\nCONTEXTO DEL MUNDO (respeta estas reglas estrictamente):\n{ctx}"

    length_rule = _LENGTH_RULE.get(text_length, _LENGTH_RULE["normal"])
    return f"{world_desc}{ctx_section}\n\n{length_rule}\n{_FORMAT_RULES}"


def build_intro_prompt(player: dict) -> str:
    level = int(player.get("level", 1))
    return (
        f"Personaje: {player['name']} | Nivel: {level}\n"
        f"Inventario: {_fmt_inventory(player.get('inventory', []))}\n\n"
        f"Inicio de la aventura. Crea la escena de apertura.\n"
        f"Establece dónde está el personaje y qué situación enfrenta.\n\n"
        f"Comienza:"
    )


def build_story_prompt(player: dict, action: str) -> str:
    level       = int(player.get("level", 1))
    old_summary = player.get("story_summary") or "La aventura acaba de comenzar."
    recent      = player.get("recent_events", [])
    npc_reg     = player.get("npc_registry", {})

    level_note = ""
    if level >= 5:
        level_note = f"Nivel {level} (experto): el personaje es reconocido, las situaciones son más complejas."
    elif level >= 3:
        level_note = f"Nivel {level}: algunos NPCs reconocen al personaje."

    recent_text = ""
    if recent:
        recent_text = "Acciones recientes:\n" + "\n".join(f"- {e}" for e in recent[-_RECENT_WINDOW:])

    npc_text = ""
    if npc_reg:
        npc_text = "Personajes conocidos (mantén su descripción exacta):\n"
        npc_text += "\n".join(f"- {name}: {desc}" for name, desc in list(npc_reg.items())[:10])

    return (
        f"Personaje: {player['name']} | Nivel: {level}\n"
        f"Inventario: {_fmt_inventory(player.get('inventory', []))}\n"
        f"{level_note}\n\n"
        f"{npc_text}\n\n"
        f"Resumen de la historia:\n{old_summary}\n\n"
        f"{recent_text}\n\n"
        f"Acción: {action}\n\n"
        f"IMPORTANTE: no repitas situaciones del historial. Avanza la trama.\n\n"
        f"Continúa:"
    )


def build_advance_prompt(player: dict) -> str:
    level       = int(player.get("level", 1))
    old_summary = player.get("story_summary") or "La aventura acaba de comenzar."
    recent      = player.get("recent_events", [])
    npc_reg     = player.get("npc_registry", {})
    recent_text = "\n".join(f"- {e}" for e in recent[-_RECENT_WINDOW:]) if recent else ""
    npc_text    = "\n".join(f"- {n}: {d}" for n, d in list(npc_reg.items())[:8]) if npc_reg else ""

    return (
        f"Personaje: {player['name']} | Nivel: {level}\n\n"
        f"Personajes conocidos:\n{npc_text}\n\n"
        f"Resumen: {old_summary}\n\n"
        f"Reciente: {recent_text}\n\n"
        f"El jugador quiere saltar a la siguiente escena importante.\n"
        f"OBLIGATORIO: cambia completamente de ubicación o situación. "
        f"Introduce un giro, una revelación o un nuevo personaje clave. "
        f"No repitas nada del historial.\n\n"
        f"Nueva escena:"
    )


def build_theme_transition_prompt(player: dict, new_theme: str, new_theme_desc: str) -> str:
    level       = int(player.get("level", 1))
    old_summary = player.get("story_summary") or "La aventura acaba de comenzar."
    recent      = player.get("recent_events", [])
    recent_text = "\n".join(f"- {e}" for e in recent[-_RECENT_WINDOW:]) if recent else ""

    return (
        f"Personaje: {player['name']} | Nivel: {level}\n\n"
        f"Historia hasta ahora:\n{old_summary}\n\n"
        f"Reciente:\n{recent_text}\n\n"
        f"El mundo cambia hacia: {new_theme_desc}.\n"
        f"Escribe una transición narrativa inmersiva (sueño, portal, salto temporal, revelación). "
        f"Al final el personaje debe estar en el nuevo mundo.\n\n"
        f"Transición:"
    )


def build_compression_prompt(summary: str) -> str:
    return (
        f"Resume el siguiente historial de historia en máximo 4 oraciones. "
        f"Conserva los puntos más importantes: personajes clave, decisiones cruciales y el estado actual.\n\n"
        f"Historial:\n{summary}\n\n"
        f"Resumen comprimido:"
    )


def _fmt_inventory(items: list) -> str:
    return ", ".join(items) if items else "vacío"
