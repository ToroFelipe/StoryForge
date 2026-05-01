"""
Servicio de IA unificado.
Soporta Ollama (local) y Groq (nube).
El proveedor se elige con AI_PROVIDER en .env
"""
import re
import httpx
from config import AI_PROVIDER, OLLAMA_URL, OLLAMA_MODEL, GROQ_API_KEY, GROQ_MODEL

DEFAULT_CHOICES = ["Explorar el área", "Hablar con alguien cercano", "Seguir el camino"]

# Modelos disponibles por proveedor
AVAILABLE_MODELS = {
    "ollama": {
        "llama3.1:8b":  "🦙 Llama 3.1 8b",
        "qwen2.5:7b":   "🌟 Qwen 2.5 7b (recomendado)",
        "qwen2.5:3b":   "⚡ Qwen 2.5 3b (rápido)",
        "mistral:7b":   "🌀 Mistral 7b",
        "gemma2:9b":    "💎 Gemma 2 9b",
    },
    "groq": {
        "llama-3.1-8b-instant":    "⚡ Llama 3.1 8b (rápido)",
        "llama-3.3-70b-versatile": "🌟 Llama 3.3 70b (mejor calidad)",
        "mixtral-8x7b-32768":      "🌀 Mixtral 8x7b",
        "gemma2-9b-it":            "💎 Gemma 2 9b",
    },
}


def get_default_model() -> str:
    return GROQ_MODEL if AI_PROVIDER == "groq" else OLLAMA_MODEL


def get_models_for_ui() -> dict:
    return AVAILABLE_MODELS.get(AI_PROVIDER, AVAILABLE_MODELS["ollama"])


async def generate_story(prompt: str, system: str, model: str = "") -> dict:
    model = model or get_default_model()
    try:
        if AI_PROVIDER == "groq":
            raw = await _call_groq(prompt, system, model)
        else:
            raw = await _call_ollama(prompt, system, model)
        return _parse(raw)
    except httpx.ConnectError:
        return _error("⚠️ El proveedor de IA no responde. Verificá tu conexión.")
    except httpx.TimeoutException:
        return _error("⏳ El narrador tardó demasiado. Intentá de nuevo.")
    except Exception as e:
        return _error(f"⚠️ Error inesperado: {str(e)[:80]}")


async def compress_summary(summary: str, model: str = "") -> str:
    from prompts import build_compression_prompt
    model  = model or get_default_model()
    system = "Eres un asistente que resume historias de forma concisa y precisa."
    prompt = build_compression_prompt(summary)
    try:
        if AI_PROVIDER == "groq":
            raw = await _call_groq(prompt, system, model)
        else:
            raw = await _call_ollama(prompt, system, model)
        return raw.strip()[:1200]
    except Exception:
        return summary[-1200:]


# ─── Proveedores ───────────────────────────────────────────────────────────────

async def _call_ollama(prompt: str, system: str, model: str) -> str:
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


async def _call_groq(prompt: str, system: str, model: str) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY no configurada en .env")

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system",  "content": system},
                    {"role": "user",    "content": prompt},
                ],
                "temperature": 0.82,
                "max_tokens":  1024,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ─── Parser ────────────────────────────────────────────────────────────────────

def _parse(text: str) -> dict:
    result = {
        "narration": "",
        "choices":   DEFAULT_CHOICES[:],
        "summary":   "",
        "new_npcs":  {},
    }

    narration_m = re.search(r"NARRACIÓN:\s*(.*?)(?=OPCIONES:|$)", text, re.S | re.I)
    if narration_m:
        result["narration"] = narration_m.group(1).strip()

    choices_m = re.search(r"OPCIONES:\s*(.*?)(?=PERSONAJES:|RESUMEN:|$)", text, re.S | re.I)
    if choices_m:
        found = re.findall(r"^\d+\.\s*(.+)", choices_m.group(1), re.M)
        if len(found) >= 2:
            result["choices"] = [str(c).strip() for c in found[:3]]

    npc_m = re.search(r"PERSONAJES:\s*(.*?)(?=RESUMEN:|$)", text, re.S | re.I)
    if npc_m:
        block = npc_m.group(1).strip()
        if "ninguno" not in block.lower():
            for line in block.splitlines():
                line = line.strip().lstrip("- ")
                if ":" in line:
                    name, _, desc = line.partition(":")
                    name, desc = name.strip(), desc.strip()
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
