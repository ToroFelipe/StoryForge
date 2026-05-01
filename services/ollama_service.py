import re
import httpx
from config import OLLAMA_URL, OLLAMA_MODEL

DEFAULT_CHOICES = ["Explorar el área", "Hablar con alguien cercano", "Seguir el camino"]


async def generate_story(prompt: str, system: str, model: str = "") -> dict:
    try:
        raw = await _call(prompt, system, model or OLLAMA_MODEL)
        return _parse(raw)
    except httpx.ConnectError:
        return _error("⚠️ Ollama no responde. Asegurate de que esté corriendo y reintentá.")
    except httpx.TimeoutException:
        return _error("⏳ El narrador tardó demasiado. Intentá de nuevo.")
    except Exception:
        return _error("⚠️ Error inesperado. Intentá de nuevo.")


async def compress_summary(summary: str, model: str = "") -> str:
    """Llama a Ollama para comprimir el resumen de la historia."""
    from prompts import build_compression_prompt
    prompt = build_compression_prompt(summary)
    system = "Eres un asistente que resume historias de forma concisa y precisa."
    try:
        raw = await _call(prompt, system, model or OLLAMA_MODEL)
        return raw.strip()[:1200]
    except Exception:
        return summary[-1200:]  # fallback: truncar


async def _call(prompt: str, system: str, model: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature":    0.82,
                    "top_p":          0.9,
                    "repeat_penalty": 1.15,
                    "num_ctx":        4096,
                },
            },
        )
        r.raise_for_status()
        return r.json().get("response", "")


def _parse(text: str) -> dict:
    result = {
        "narration": "",
        "choices":   DEFAULT_CHOICES[:],
        "summary":   "",
        "new_npcs":  {},   # {name: description}
    }

    narration_m = re.search(r"NARRACIÓN:\s*(.*?)(?=OPCIONES:|$)", text, re.S | re.I)
    if narration_m:
        result["narration"] = narration_m.group(1).strip()

    choices_m = re.search(r"OPCIONES:\s*(.*?)(?=PERSONAJES:|RESUMEN:|$)", text, re.S | re.I)
    if choices_m:
        found = re.findall(r"^\d+\.\s*(.+)", choices_m.group(1), re.M)
        if len(found) >= 2:
            result["choices"] = [str(c).strip() for c in found[:3]]

    # Parsear personajes nuevos
    npc_m = re.search(r"PERSONAJES:\s*(.*?)(?=RESUMEN:|$)", text, re.S | re.I)
    if npc_m:
        npc_block = npc_m.group(1).strip()
        if "ninguno" not in npc_block.lower():
            for line in npc_block.splitlines():
                line = line.strip().lstrip("- ")
                if ":" in line:
                    name, _, desc = line.partition(":")
                    name = name.strip()
                    desc = desc.strip()
                    if name and desc and len(name) < 40:
                        result["new_npcs"][name] = desc

    summary_m = re.search(r"RESUMEN:\s*(.+)", text, re.S | re.I)
    if summary_m:
        result["summary"] = summary_m.group(1).strip()[:600]

    if not result["narration"]:
        result["narration"] = text[:1200].strip()

    return result


def _error(msg: str) -> dict:
    return {
        "narration": msg,
        "choices":   ["Reintentar", "Explorar el área", "Descansar"],
        "summary":   "",
        "new_npcs":  {},
    }
