import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")

# ── Proveedor de IA ───────────────────────────────────────
AI_PROVIDER      = os.getenv("AI_PROVIDER", "ollama").lower()  # "ollama" | "groq"

# Ollama (local)
OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# Groq (nube)
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL       = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# WordPress
WP_URL           = os.getenv("WP_URL", "https://codigosamurai.cl")
WP_USER          = os.getenv("WP_USER")
WP_APP_PASSWORD  = os.getenv("WP_APP_PASSWORD")
