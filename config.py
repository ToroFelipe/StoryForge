import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
WP_URL           = os.getenv("WP_URL", "https://codigosamurai.cl")
WP_USER          = os.getenv("WP_USER")
WP_APP_PASSWORD  = os.getenv("WP_APP_PASSWORD")
