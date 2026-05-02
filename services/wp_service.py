import asyncio
import logging
import base64
import httpx
from config import WP_URL, WP_USER, WP_APP_PASSWORD

logger = logging.getLogger(__name__)

_BASE    = f"{WP_URL}/wp-json/storyforge/v1"
_TIMEOUT = 30.0

# Si WP no está disponible, los datos se guardan solo en memoria
_WP_ENABLED = bool(WP_URL and WP_USER and WP_APP_PASSWORD)


def _headers() -> dict:
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def _log_wp_error(action: str, e: Exception):
    logger.warning(
        "WP error %s — %s: %s | URL base: %s",
        action, type(e).__name__, str(e) or "(sin mensaje)", _BASE,
    )


async def get_player(telegram_id: int) -> dict | None:
    if not _WP_ENABLED:
        logger.info("WP deshabilitado (faltan variables) — get_player ignorado")
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"{_BASE}/player/{telegram_id}", headers=_headers())
            if r.status_code == 404:
                return None
            if not r.is_success:
                logger.warning("WP get_player HTTP %s: %s", r.status_code, r.text[:120])
                return None
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        logger.warning("WP timeout al buscar jugador %s — tratando como nuevo", telegram_id)
        return None
    except Exception as e:
        _log_wp_error("get_player", e)
        return None


async def _create_player_bg(data: dict):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(f"{_BASE}/player", json=data, headers=_headers())
            if not r.is_success:
                logger.warning("WP create_player HTTP %s: %s", r.status_code, r.text[:120])
    except Exception as e:
        _log_wp_error("create_player", e)


async def create_player(data: dict) -> bool:
    """Lanza el guardado en segundo plano para no bloquear al jugador."""
    if not _WP_ENABLED:
        return True
    asyncio.create_task(_create_player_bg(data))
    return True


async def _update_player_bg(telegram_id: int, data: dict):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.put(
                f"{_BASE}/player/{telegram_id}", json=data, headers=_headers()
            )
            if not r.is_success:
                logger.warning("WP update_player HTTP %s: %s", r.status_code, r.text[:120])
    except Exception as e:
        _log_wp_error("update_player", e)


async def update_player(telegram_id: int, data: dict) -> bool:
    """Lanza el guardado en segundo plano para no bloquear al jugador."""
    if not _WP_ENABLED:
        return True
    asyncio.create_task(_update_player_bg(telegram_id, data))
    return True


async def delete_player(telegram_id: int) -> bool:
    if not _WP_ENABLED:
        return True
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.delete(
                f"{_BASE}/player/{telegram_id}", headers=_headers()
            )
            if not r.is_success:
                logger.warning("WP delete_player HTTP %s: %s", r.status_code, r.text[:120])
            return r.is_success
    except Exception as e:
        _log_wp_error("delete_player", e)
        return False
