import base64
import httpx
from config import WP_URL, WP_USER, WP_APP_PASSWORD

_BASE = f"{WP_URL}/wp-json/storyforge/v1"


def _headers() -> dict:
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


async def get_player(telegram_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{_BASE}/player/{telegram_id}", headers=_headers())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def create_player(data: dict) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{_BASE}/player", json=data, headers=_headers())
        return r.is_success


async def update_player(telegram_id: int, data: dict) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.put(f"{_BASE}/player/{telegram_id}", json=data, headers=_headers())
        return r.is_success


async def delete_player(telegram_id: int) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(f"{_BASE}/player/{telegram_id}", headers=_headers())
        return r.is_success
