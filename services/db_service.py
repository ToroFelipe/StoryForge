"""
Servicio de persistencia con PostgreSQL (Railway).
Reemplaza wp_service.py — no requiere plugin externo.
Si DATABASE_URL no está configurada, el bot corre en modo memoria (sin persistencia).
"""
import json as _json
import logging
import os

logger = logging.getLogger(__name__)

try:
    import asyncpg
    _ASYNCPG_OK = True
except ImportError:
    _ASYNCPG_OK = False
    logger.warning("asyncpg no instalado — modo memoria activo")

_pool = None   # asyncpg.Pool

# Campos que se almacenan como JSONB
_JSON_FIELDS = {"inventory", "npc_registry", "recent_events"}

# Campos válidos de la tabla (evita SQL injection en update dinámico)
_VALID_COLUMNS = {
    "name", "theme", "custom_theme", "text_length",
    "level", "experience", "story_summary", "current_chapter",
    "inventory", "model", "context_key", "npc_registry", "recent_events",
}


# ─── Inicialización ────────────────────────────────────────────────────────────

async def init_db() -> bool:
    global _pool
    if not _ASYNCPG_OK:
        return False

    url = os.getenv("DATABASE_URL", "")
    if not url:
        logger.warning("DATABASE_URL no configurada — datos solo en memoria")
        return False

    try:
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    telegram_id   BIGINT  PRIMARY KEY,
                    name          TEXT    NOT NULL,
                    theme         TEXT    NOT NULL DEFAULT 'fantasy',
                    custom_theme  TEXT    NOT NULL DEFAULT '',
                    text_length   TEXT    NOT NULL DEFAULT 'normal',
                    level         INTEGER NOT NULL DEFAULT 1,
                    experience    INTEGER NOT NULL DEFAULT 0,
                    story_summary TEXT    NOT NULL DEFAULT '',
                    current_chapter TEXT  NOT NULL DEFAULT 'inicio',
                    inventory     JSONB   NOT NULL DEFAULT '[]',
                    model         TEXT    NOT NULL DEFAULT '',
                    context_key   TEXT    NOT NULL DEFAULT '',
                    npc_registry  JSONB   NOT NULL DEFAULT '{}',
                    recent_events JSONB   NOT NULL DEFAULT '[]'
                )
            """)
        logger.info("PostgreSQL conectado y tabla lista")
        return True
    except Exception as e:
        logger.error("Error conectando PostgreSQL: %s: %s", type(e).__name__, e)
        _pool = None
        return False


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convierte una fila de asyncpg a dict con tipos correctos."""
    d = dict(row)
    for field in _JSON_FIELDS:
        val = d.get(field)
        if isinstance(val, str):
            try:
                d[field] = _json.loads(val)
            except Exception:
                d[field] = {} if field == "npc_registry" else []
        elif val is None:
            d[field] = {} if field == "npc_registry" else []
    # Asegurar tipos numéricos
    d["level"]      = int(d.get("level", 1))
    d["experience"] = int(d.get("experience", 0))
    return d


def _encode(key: str, value):
    """Serializa valores JSON para INSERT/UPDATE."""
    if key in _JSON_FIELDS and not isinstance(value, str):
        return _json.dumps(value)
    return value


# ─── CRUD ─────────────────────────────────────────────────────────────────────

async def get_player(telegram_id: int) -> dict | None:
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM players WHERE telegram_id = $1", telegram_id
            )
        return _row_to_dict(row) if row else None
    except Exception as e:
        logger.warning("DB error get_player: %s: %s", type(e).__name__, e)
        return None


async def create_player(data: dict) -> bool:
    if not _pool:
        return True
    try:
        async with _pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO players (
                    telegram_id, name, theme, custom_theme, text_length,
                    level, experience, story_summary, current_chapter,
                    inventory, model, context_key, npc_registry, recent_events
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT (telegram_id) DO NOTHING
            """,
                int(data["telegram_id"]),
                data.get("name", ""),
                data.get("theme", "fantasy"),
                data.get("custom_theme", ""),
                data.get("text_length", "normal"),
                int(data.get("level", 1)),
                int(data.get("experience", 0)),
                data.get("story_summary", ""),
                data.get("current_chapter", "inicio"),
                _json.dumps(data.get("inventory", [])),
                data.get("model", ""),
                data.get("context_key", ""),
                _json.dumps(data.get("npc_registry", {})),
                _json.dumps(data.get("recent_events", [])),
            )
        logger.info("DB create_player OK — telegram_id=%s", data["telegram_id"])
        return True
    except Exception as e:
        logger.warning("DB error create_player: %s: %s", type(e).__name__, e)
        return False


async def update_player(telegram_id: int, data: dict) -> bool:
    if not _pool or not data:
        return True

    # Filtrar solo columnas válidas
    filtered = {k: v for k, v in data.items() if k in _VALID_COLUMNS}
    if not filtered:
        return True

    try:
        parts  = [f"{k} = ${i+2}" for i, k in enumerate(filtered)]
        values = [_encode(k, v) for k, v in filtered.items()]
        query  = f"UPDATE players SET {', '.join(parts)} WHERE telegram_id = $1"

        async with _pool.acquire() as conn:
            await conn.execute(query, telegram_id, *values)
        return True
    except Exception as e:
        logger.warning("DB error update_player: %s: %s", type(e).__name__, e)
        return False


async def delete_player(telegram_id: int) -> bool:
    if not _pool:
        return True
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM players WHERE telegram_id = $1", telegram_id
            )
        return True
    except Exception as e:
        logger.warning("DB error delete_player: %s: %s", type(e).__name__, e)
        return False
