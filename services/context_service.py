from pathlib import Path

CONTEXT_DIR     = Path(__file__).parent.parent / "context"
MAX_CHARS       = 2000   # tope para no saturar el contexto del modelo


def list_files() -> list[dict]:
    """Devuelve los archivos .txt disponibles en la carpeta context/."""
    if not CONTEXT_DIR.exists():
        return []
    files = []
    for f in sorted(CONTEXT_DIR.glob("*.txt")):
        files.append({
            "key":   f.stem,                              # "pokemon"
            "label": f.stem.replace("_", " ").title(),   # "Pokemon"
            "path":  f,
        })
    return files


def load(key: str) -> str:
    """Carga el contenido de context/<key>.txt (máx MAX_CHARS caracteres)."""
    if not key:
        return ""
    path = CONTEXT_DIR / f"{key}.txt"
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + "\n[...contexto truncado...]"
    return content


def has_files() -> bool:
    return bool(list_files())
