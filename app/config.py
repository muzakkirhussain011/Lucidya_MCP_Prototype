# file: app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3:0.6b")

# Vector Store
VECTOR_INDEX_PATH = os.getenv("VECTOR_INDEX_PATH", str(DATA_DIR / "faiss.index"))
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# MCP Servers
MCP_SEARCH_PORT = int(os.getenv("MCP_SEARCH_PORT", "9001"))
MCP_EMAIL_PORT = int(os.getenv("MCP_EMAIL_PORT", "9002"))
MCP_CALENDAR_PORT = int(os.getenv("MCP_CALENDAR_PORT", "9003"))
MCP_STORE_PORT = int(os.getenv("MCP_STORE_PORT", "9004"))

# Compliance
COMPANY_FOOTER_PATH = os.getenv("COMPANY_FOOTER_PATH", str(DATA_DIR / "footer.txt"))
ENABLE_CAN_SPAM = os.getenv("ENABLE_CAN_SPAM", "true").lower() == "true"
ENABLE_PECR = os.getenv("ENABLE_PECR", "true").lower() == "true"
ENABLE_CASL = os.getenv("ENABLE_CASL", "true").lower() == "true"

# Scoring
MIN_FIT_SCORE = float(os.getenv("MIN_FIT_SCORE", "0.5"))
FACT_TTL_HOURS = int(os.getenv("FACT_TTL_HOURS", "168"))  # 1 week

# Data Files
COMPANIES_FILE = DATA_DIR / "companies.json"
SUPPRESSION_FILE = DATA_DIR / "suppression.json"